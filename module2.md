# Module 2 — Module Planner
## Detailed Implementation Plan

Goal for this module: user picks a topic ("module") from their syllabus, dumps raw text about what resources they'll use and how much time they have, and the system produces an AI-generated day-by-day master plan for that module — stored, browsable, and ready for Module 3 to execute against.

This builds directly on Module 1's `topics` table and reuses the exact same architecture (FastAPI + async SQLAlchemy + Pydantic-validated AI calls). No new tech stack decisions needed here — the interesting part is the **pipeline design**, not new libraries.

---

## 1. What's New vs Module 1 (Dependencies)

No new core libraries. Two additions worth calling out:

```
apscheduler   # optional, only if you want scheduled/background regeneration later — 
              # not required for Module 2's synchronous flow, see section 5
```

You will **not** need Celery/Redis yet — Module 2's AI calls (resource parsing, master plan generation) are still single-request, single-response operations triggered by explicit user actions, same pattern as Module 1's parse/enrich. Keep using `BackgroundTasks` + polling if generation takes more than a couple seconds.

---

## 2. New Database Tables in Play

(Already defined in the schema doc — just listing what this module writes to.)

- `module_starts` — the raw input record when a user starts a module
- `module_plans` — the AI-generated master plan (one per module start)
- `module_plan_days` — individual days within a master plan
- `module_resources` — parsed resources linked to a module start
- `resources` — reused from Module 1, but now populated by AI extraction instead of manual entry

---

## 3. Project Structure Additions

```
backend/
  app/
    models/
      module_start.py
      module_plan.py
      module_plan_day.py
      module_resource.py
    schemas/
      module_start.py
      module_plan.py
      ai_resource_parser.py       # schema for agent output
      ai_planner.py                # schema for agent output
    api/
      routes/
        modules.py                 # start module, get plan, list module history
    services/
      module_service.py            # orchestration: start -> parse resources -> generate plan
      ai/
        resource_parser.py         # new agent
        planner.py                  # new agent (the "Planner" from prompt doc)
        prompts/
          resource_parser.txt
          planner.txt
    tests/
      test_module_start.py
      test_resource_parsing.py
      test_planner.py

frontend/
  src/
    pages/
      ModuleStartPage.tsx           # topic selected -> raw input form
      ModulePlanReviewPage.tsx       # shows generated day-by-day plan, allows edits
      ModuleListPage.tsx             # current + past modules
    components/
      DayPlanCard.tsx
      ResourceList.tsx
```

---

## 4. Pipeline Architecture

This is the core design decision for Module 2. Think of it as **one orchestrated pipeline with two sequential AI stages**, not two independent features:

```
User selects topic (from Module 1's topic tree)
        │
        ▼
User submits raw text: resources + expected hours + daily hours available
        │
        ▼
┌───────────────────────────────────────────┐
│ STAGE 1: Resource Parser (agent)            │
│ raw text -> structured resources JSON       │
└───────────────────────────────────────────┘
        │
        ▼
Backend persists: module_starts row + resources rows + module_resources links
        │
        ▼
┌───────────────────────────────────────────┐
│ Backend assembles planning context:         │
│  - topic + subtopics (from Module 1)        │
│  - parsed resources (from Stage 1)          │
│  - days_remaining (exam_date - today)       │
│  - overall_completion_pct (SQL query)       │
│  - daily_hours_available (user input)       │
└───────────────────────────────────────────┘
        │
        ▼
┌───────────────────────────────────────────┐
│ STAGE 2: Planner (agent)                    │
│ context -> day-by-day master plan JSON      │
└───────────────────────────────────────────┘
        │
        ▼
Backend persists: module_plans row + module_plan_days rows (one transaction)
        │
        ▼
User reviews plan (can regenerate with adjusted hours, or accept)
        │
        ▼
Module ready for Module 3 to execute
```

**Why two separate stages instead of one combined prompt:** resource parsing and day-planning are different reasoning tasks with different failure modes. If you combine them, a bad resource extraction silently corrupts the plan and you can't tell which stage went wrong. Keeping them separate means each has its own validation checkpoint, its own retry logic, and — importantly — the user can review parsed resources before the (more expensive, more important) planning stage runs on top of them.

### 4.1 Orchestration lives in `module_service.py`, not in route handlers

```python
# services/module_service.py

async def start_module(db, user, topic_id: UUID, raw_input: dict) -> ModuleStart:
    topic = await topic_service.get_owned_topic(db, user, topic_id)  # ownership check

    module_start = ModuleStart(
        topic_id=topic.id,
        exam_id=topic.exam_id,
        raw_input=raw_input["raw_text"],
        expected_hours=raw_input.get("expected_hours"),
        daily_hours_available=raw_input["daily_hours_available"],
        status="planning",
    )
    db.add(module_start)
    await db.flush()  # get module_start.id without committing yet

    # Stage 1
    parsed_resources = await resource_parser.parse(
        raw_text=raw_input["raw_text"],
        topic_name=topic.name,
    )
    await _persist_resources(db, module_start, parsed_resources)

    # Stage 2 — build context, then generate
    context = await _build_planning_context(db, topic, module_start)
    plan = await planner.generate_plan(context)
    await _persist_plan(db, module_start, plan)

    module_start.status = "active"
    await db.commit()
    return module_start
```

Key pattern: **the whole pipeline is one service function, wrapped in one transaction scope**, but each AI call is its own logged, validated, retryable unit internally (reusing the `log_ai_call` wrapper and validation pattern from Module 1). If Stage 2 fails after Stage 1 succeeded, you roll back the whole thing rather than leaving an orphaned `module_start` with resources but no plan — a half-finished module is confusing UX and bad data to build Module 3 against.

### 4.2 Building the planning context — this is where correctness matters most

```python
async def _build_planning_context(db, topic, module_start) -> PlannerContext:
    exam = await exam_service.get(db, topic.exam_id)

    days_remaining = (exam.exam_date - date.today()).days if exam.exam_date else None

    overall_completion = await topic_service.get_exam_completion_pct(db, exam.id)

    subtopics = await topic_service.get_subtree(db, topic.id)  # reuses Module 1's recursive fetch

    resources = await module_resource_service.list_for_module(db, module_start.id)

    return PlannerContext(
        exam_name=exam.name,
        exam_date=exam.exam_date,
        days_remaining=days_remaining,
        overall_completion_pct=overall_completion,
        topic_name=topic.name,
        subtopics=subtopics,
        raw_module_input_text=module_start.raw_input,
        module_resources=resources,
        daily_hours_available=module_start.daily_hours_available,
        expected_hours=module_start.expected_hours,
    )
```

Notice this pulls from **three different sources**: Module 1's topic tree (for subtopic difficulty/hours), this module's own resource parsing output, and a live SQL computation (completion %, days remaining). This is the "student model" principle from the original design — the planner should never plan in a vacuum, always against real current state, computed fresh at generation time, not cached from whenever the exam was created.

---

## 5. Handling Generation Latency

Planning calls are heavier than Module 1's parsing (more context, more reasoning about sequencing) and may take 5-15 seconds. Two things to get right:

**A. Don't block the HTTP request.**

```
POST /modules/start          -> creates module_start (status=planning), 
                                  kicks off pipeline via BackgroundTasks, 
                                  returns { module_start_id } immediately (202 Accepted)

GET /modules/{id}/status      -> frontend polls every 1.5-2s
                                  returns { status: "planning" | "active" | "failed", error?: string }

GET /modules/{id}/plan         -> once status=active, returns full plan
```

Frontend shows a loading state on `ModuleStartPage` ("Building your plan...") while polling, then navigates to `ModulePlanReviewPage` once ready. Same pattern as Module 1's parse/enrich polling — reuse the polling hook you already built (`useAIJobStatus` or similar) rather than writing this twice.

**B. If Stage 1 succeeds but Stage 2 fails, don't discard Stage 1's work.**

Set `module_start.status = 'planning_failed'` (not just a generic failure) and expose a `POST /modules/{id}/retry-plan` endpoint that re-runs only Stage 2 using the already-parsed resources. Re-parsing resources on every retry wastes an AI call and risks getting a *different* resource extraction each time, which would be confusing if the user already reviewed it.

---

## 6. Resource Parser — Implementation Detail

```python
# services/ai/resource_parser.py

async def parse(raw_text: str, topic_name: str) -> ParsedResourcesResponse:
    user_message = f"Topic: {topic_name}\nStudent's raw resource/plan description:\n\"\"\"\n{raw_text}\n\"\"\""
    raw_response = await call_claude(RESOURCE_PARSER_SYSTEM_PROMPT, user_message)
    return await validate_with_retry(
        raw_response, ParsedResourcesResponse, RESOURCE_PARSER_SYSTEM_PROMPT, user_message
    )
```

Pull the "parse, validate, retry-once-with-error" logic from Module 1 into a shared helper now (`services/ai/validation.py::validate_with_retry`) instead of copy-pasting it per agent — you now have four agents built (parser, estimator, resource parser, planner) that all need this exact same pattern, and it only grows from here.

```python
# services/ai/validation.py
async def validate_with_retry(raw_response: str, schema_cls, system_prompt: str, user_message: str):
    try:
        return schema_cls.model_validate(json.loads(raw_response))
    except (json.JSONDecodeError, ValidationError) as e:
        retry_prompt = f"{user_message}\n\nYour previous response failed validation: {e}\nReturn corrected JSON only."
        raw_response = await call_claude(system_prompt, retry_prompt)
        return schema_cls.model_validate(json.loads(raw_response))  # let it raise if still bad
```

**Persisting parsed resources:**

```python
async def _persist_resources(db, module_start, parsed: ParsedResourcesResponse):
    for r in parsed.resources:
        resource = Resource(
            exam_id=module_start.exam_id,
            topic_id=module_start.topic_id,
            type=r.type, title=r.title, source_name=r.source_name,
            url=r.url, total_units=r.total_units,
        )
        db.add(resource)
        await db.flush()
        db.add(ModuleResource(
            module_start_id=module_start.id,
            resource_id=resource.id,
            units_planned=r.total_units,
            units_completed=0,
        ))
```

---

## 7. Planner — Implementation Detail

```python
# services/ai/planner.py

async def generate_plan(context: PlannerContext) -> MasterPlanResponse:
    user_message = _build_planner_user_message(context)  # template from prompt doc
    raw_response = await call_claude(PLANNER_SYSTEM_PROMPT, user_message, model="claude-sonnet-4-6")
    plan = await validate_with_retry(raw_response, MasterPlanResponse, PLANNER_SYSTEM_PROMPT, user_message)
    _validate_plan_constraints(plan, context)  # see below
    return plan
```

**Critical addition: validate business constraints, not just JSON shape.**

Pydantic validation only confirms the JSON is *structurally* correct (right fields, right types). It does not confirm the plan is *sane* against the constraints described in the prompt (e.g. "total days must respect days_remaining", "don't exceed daily hours by >10%"). Add an explicit post-validation check:

```python
def _validate_plan_constraints(plan: MasterPlanResponse, context: PlannerContext):
    if context.days_remaining and plan.total_days > context.days_remaining:
        raise PlanConstraintError(
            f"Generated plan spans {plan.total_days} days but only "
            f"{context.days_remaining} days remain before the exam."
        )
    for day in plan.days:
        if day.planned_hours > context.daily_hours_available * 1.1:
            raise PlanConstraintError(
                f"Day {day.day_number} plans {day.planned_hours}h, exceeding "
                f"the {context.daily_hours_available}h budget by more than 10%."
            )
```

If this raises, retry the generation once with the violation appended to the prompt (same pattern as JSON validation retry, different failure class). This is important: **an AI that returns syntactically valid but logically wrong JSON is a more dangerous failure mode than one that returns malformed JSON**, because it won't get caught by Pydantic and will silently produce a bad plan. Don't skip this step.

**Persisting the plan:**

```python
async def _persist_plan(db, module_start, plan: MasterPlanResponse):
    module_plan = ModulePlan(
        module_start_id=module_start.id,
        total_days=plan.total_days,
        ai_raw_response=plan.model_dump(),
        generated_at=datetime.utcnow(),
    )
    db.add(module_plan)
    await db.flush()

    for day in plan.days:
        db.add(ModulePlanDay(
            module_plan_id=module_plan.id,
            day_number=day.day_number,
            planned_date=module_start.started_at.date() + timedelta(days=day.day_number - 1),
            focus_topics=day.focus_subtopics,
            planned_hours=day.planned_hours,
            status="pending",
        ))
```

---

## 8. API Endpoints Summary

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/modules/start` | Kick off pipeline for a topic (async, returns immediately) |
| `GET` | `/modules/{id}/status` | Poll pipeline status |
| `GET` | `/modules/{id}/plan` | Get full master plan once ready |
| `POST` | `/modules/{id}/retry-plan` | Re-run Stage 2 only, using existing parsed resources |
| `PATCH` | `/modules/{id}/plan` | User manually edits a day's plan before accepting (optional, see below) |
| `GET` | `/exams/{id}/modules` | List all module starts for an exam (current + past) |
| `GET` | `/modules/{id}` | Single module detail (resources + plan + status) |

**On `PATCH /modules/{id}/plan`:** decide early whether you want to allow manual editing of the AI-generated plan before it's "locked in" for Module 3 to execute against. Recommended: yes, at minimum letting the user reorder/adjust `planned_hours` per day, same principle as Module 1's topic-tree review step — AI gets it close, user gets final say before commitment.

---

## 9. Concurrency & Performance Considerations

- **Resource parsing and difficulty context fetching can run in parallel** where they don't depend on each other — e.g., while Stage 1 (resource parsing) is running, you can already fetch the topic's subtree and completion % in parallel via `asyncio.gather`, since neither depends on parsed resources. Only Stage 2 needs to wait for both.

```python
resources_task = asyncio.create_task(resource_parser.parse(raw_input["raw_text"], topic.name))
subtree_task = asyncio.create_task(topic_service.get_subtree(db, topic.id))
completion_task = asyncio.create_task(topic_service.get_exam_completion_pct(db, exam.id))

parsed_resources, subtopics, overall_completion = await asyncio.gather(
    resources_task, subtree_task, completion_task
)
```

- **Rate limiting:** if a user starts multiple modules back-to-back (unlikely but possible — e.g. batch-planning several chapters), reuse the same bounded semaphore pattern from Module 1's enrichment step.
- **Idempotency:** if the frontend retries `POST /modules/start` due to a network blip, you don't want two module starts for the same topic+input. Consider a short-lived idempotency key (client-generated UUID passed in the request, checked against a recent-requests cache) — not critical for an MVP, but worth a `# TODO` if you skip it now.

---

## 10. Testing Strategy

- **Unit test the pipeline stages independently** with fixed fixture inputs (don't call the real AI in tests) — mock `call_claude` to return a canned valid JSON string, and separately a canned invalid one, to test both the happy path and the retry path.
- **Test `_validate_plan_constraints` directly** with hand-crafted `MasterPlanResponse` objects that violate each constraint (days exceed remaining, hours exceed budget) — this is pure business logic and should have zero flakiness.
- **Integration test the full `start_module` flow** against a test DB with mocked AI responses, asserting the full chain of DB writes (module_start → resources → module_resources → module_plan → module_plan_days) happens correctly and atomically (test that a Stage 2 failure rolls back Stage 1's writes too, if you choose that transaction boundary — decide and test explicitly rather than discovering the behavior in production).

---

## 11. Suggested Build Order Within Module 2

1. New models + Alembic migration for `module_starts`, `module_plans`, `module_plan_days`, `module_resources`.
2. Resource parser agent — build against real messy "I'll watch X, read Y" text early, same reasoning as Module 1: find prompt problems before building UI around them.
3. `_persist_resources` + resource review UI (even a simple list is fine to start).
4. Planning context builder (`_build_planning_context`) — test this independently with a fixture topic, since it's pure data assembly and easy to get subtly wrong (off-by-one on days_remaining, wrong completion query, etc.).
5. Planner agent + `_validate_plan_constraints` — this is the highest-value piece to get right, spend real time iterating on the prompt against varied inputs (short deadlines, huge topics, tiny daily hours) to see where it breaks the constraints.
6. `_persist_plan` + plan review UI (`ModulePlanReviewPage`).
7. Wire up the full orchestrated `start_module` pipeline with `BackgroundTasks` + polling.
8. `retry-plan` endpoint for the Stage-2-only retry path.
9. Module list/history endpoints + `ModuleListPage`.
10. Tests: mocked-AI unit tests for each stage, integration test for the full pipeline, constraint-violation tests.

---

## 12. What NOT to Build Yet

- Daily task generation from the master plan (that's Module 3 — `daily_plans` table stays untouched here)
- Any progress tracking / completion updates from actual study (Module 3)
- Adjusting the master plan *after* it's active based on real progress (Module 3's redistribution logic) — Module 2 only produces the *initial* plan
- Celery/Redis — still not needed; `BackgroundTasks` + polling handles this module's latency fine
- Multi-module dependency planning (e.g. auto-sequencing which topic to start next) — that's implicitly Module 4 territory (analytics/recommendations), not this module

Keeping Module 2 scoped strictly to "produce one good master plan for one module" keeps it shippable — the temptation here is to start building Module 3's adaptive logic because it feels related; resist it until Module 2 is solid and testable on its own.
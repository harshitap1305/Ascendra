# Module 3 — Daily Mentor
## Detailed Implementation Plan

Goal for this module: every day, the system generates a concrete task list from the module's master plan; at night, the user reports what they actually did in free text; the system extracts structured progress, updates the database, generates mentor-style feedback, and — when needed — adjusts the *remaining* days of the plan without touching the overall day budget.

This is the module where the "mentor" feeling actually gets built. It's also the one with the most moving parts, so the architecture matters more here than anywhere else so far.

---

## 1. New Dependencies

```
apscheduler        # now actually needed — for the daily morning-generation trigger
```

Still no Celery/Redis. `APScheduler` running inside the FastAPI process (as a background job scheduler) is enough at this scale — one process, running a job once a day per active module isn't heavy load. Revisit only if you outgrow a single backend instance.

---

## 2. New Database Tables in Play

Already defined in the schema doc:

- `daily_plans` — today's concrete tasks
- `daily_reports` — raw + extracted end-of-day check-in
- `study_logs` — per-topic granular progress entries
- `feedback` — mentor's response after each check-in

Tables this module **updates** (owned by earlier modules):
- `topics.status`, `topics.completion_pct` (via the rollup function you already built in Module 1)
- `module_plan_days.status` (marks days completed/adjusted)
- `module_starts.status` (marks module completed when all days done)

---

## 3. Project Structure Additions

```
backend/
  app/
    models/
      daily_plan.py
      daily_report.py
      study_log.py
      feedback.py
    schemas/
      daily_plan.py
      daily_report.py
      ai_daily_planner.py         # agent 4 schema
      ai_progress_analyzer.py     # agent 5 schema
      ai_feedback.py              # agent 6 schema
    api/
      routes/
        daily.py                  # get today's plan, submit check-in, get feedback history
    services/
      daily_service.py            # orchestration: generate plan / process check-in
      replanning_service.py       # the deterministic compress/redistribute algorithm
      scheduler.py                # APScheduler setup, morning-generation job
      ai/
        daily_planner.py          # agent 4
        progress_analyzer.py      # agent 5
        feedback_generator.py     # agent 6
        prompts/
          daily_planner.txt
          progress_analyzer.txt
          feedback_generator.txt
    tests/
      test_daily_plan_generation.py
      test_checkin_pipeline.py
      test_replanning_algorithm.py   # the most important test file in this module

frontend/
  src/
    pages/
      TodayPage.tsx                 # today's tasks, mark progress, submit check-in
      CheckinPage.tsx               # free-text end-of-day input
      FeedbackHistoryPage.tsx
    components/
      TaskChecklist.tsx
      FeedbackCard.tsx
```

---

## 4. Two Pipelines, Two Different Trigger Models

Module 3 has two genuinely separate pipelines that people often conflate — keep them architecturally distinct:

**Pipeline A — Daily Plan Generation** (scheduled/proactive, low-stakes AI call)
**Pipeline B — End-of-Day Check-in** (user-triggered, higher-stakes: touches progress data and future plan)

```
PIPELINE A (runs once per active module, per day — scheduled)

  APScheduler job (runs at, e.g., 4 AM server time, or per-user local morning)
        │
        ▼
  For each active module_start:
    - fetch today's module_plan_day (by date, from master plan)
    - fetch yesterday's daily_plan + daily_report (if any) for carry-over
        │
        ▼
  ┌─────────────────────────────────────┐
  │ AGENT 4: Daily Planner                │
  │ master-plan-day + carry-over          │
  │   -> today's concrete task list       │
  └─────────────────────────────────────┘
        │
        ▼
  Persist daily_plans row (status=pending)
        │
        ▼
  (optional) create a `notifications` row: "Good morning, today's focus is..."


PIPELINE B (user submits free text, any time, usually evening)

  POST /daily/{daily_plan_id}/checkin  { raw_text }
        │
        ▼
  ┌─────────────────────────────────────┐
  │ AGENT 5: Progress Analyzer            │
  │ today's tasks + raw text              │
  │   -> structured completion data       │
  └─────────────────────────────────────┘
        │
        ▼
  Persist daily_reports row + study_logs rows (one per topic touched)
        │
        ▼
  Update topics.status / completion_pct (rollup, reused from Module 1)
  Update module_plan_days.status = 'completed'
        │
        ▼
  Backend computes: pace vs plan, days remaining, completion delta
  (deterministic SQL/Python — NOT the AI's job)
        │
        ▼
  ┌─────────────────────────────────────┐
  │ AGENT 6: Feedback Generator           │
  │ full student context + today's result │
  │   -> narrative feedback + flags       │
  └─────────────────────────────────────┘
        │
        ▼
  Persist feedback row
        │
        ▼
  IF feedback.adjustment_needed == true:
        │
        ▼
  ┌─────────────────────────────────────┐
  │ DETERMINISTIC REPLANNING ALGORITHM    │
  │ (backend logic, not an AI call)       │
  │ redistributes remaining               │
  │ module_plan_days                      │
  └─────────────────────────────────────┘
        │
        ▼
  Response to frontend: { feedback, updated_plan_summary? }
```

**Why the replanning step is deterministic code, not another AI call:** this is the single most important architectural decision in this module. If you let an LLM freely rewrite the remaining schedule every time a student under- or over-performs, you get schedule drift — small inconsistencies compound over weeks, the AI might silently violate the exam-date constraint, and worse, the plan becomes non-reproducible (same inputs could yield different outputs on retry). Section 6 covers the actual algorithm.

---

## 5. Pipeline A — Daily Plan Generation, In Detail

### 5.1 The scheduler

```python
# services/scheduler.py
from apscheduler.schedulers.asyncio import AsyncIOScheduler

scheduler = AsyncIOScheduler()

def start_scheduler():
    scheduler.add_job(generate_all_daily_plans, "cron", hour=4, minute=0)
    scheduler.start()

async def generate_all_daily_plans():
    async with get_db_session() as db:
        active_modules = await module_service.get_all_active_module_starts(db)
        # bounded concurrency, same pattern as Module 1/2's chunk processing
        semaphore = asyncio.Semaphore(5)
        async def generate_one(module_start):
            async with semaphore:
                try:
                    await daily_service.generate_daily_plan(db, module_start)
                except Exception as e:
                    logger.error(f"Daily plan generation failed for {module_start.id}: {e}")
                    # do NOT let one failure kill the whole batch job
        await asyncio.gather(*[generate_one(m) for m in active_modules])
```

Register `start_scheduler()` in FastAPI's lifespan startup event.

**Timezone consideration:** running one global cron at a fixed server hour is fine for an MVP with users in one region. If you have users across timezones, either (a) run the job more frequently (e.g. hourly) and only generate for users whose local time just passed midnight, or (b) explicitly punt on this for now and note it as a known limitation — don't over-build timezone-aware scheduling before you have users who need it.

**Fallback for missed generation:** also expose `GET /daily/today` to lazily generate on-demand if no `daily_plans` row exists yet for today (e.g. user opens the app before the cron ran, or the cron failed for their module). This makes the feature resilient without needing the scheduler to be perfect.

```python
# api/routes/daily.py
@router.get("/daily/today")
async def get_today_plan(module_start_id: UUID, db=Depends(get_db), user=Depends(get_current_user)):
    plan = await daily_service.get_or_generate_today_plan(db, module_start_id, user)
    return plan
```

### 5.2 Building carry-over context

```python
# services/daily_service.py
async def generate_daily_plan(db, module_start: ModuleStart) -> DailyPlan:
    today = date.today()
    plan_day = await module_plan_service.get_day_for_date(db, module_start.id, today)
    if plan_day is None:
        # module's master plan window has ended — nothing scheduled today
        return None

    yesterday_report = await daily_report_service.get_latest_for_module(db, module_start.id)
    yesterday_pending = _extract_pending_tasks(yesterday_report) if yesterday_report else []

    ai_response = await daily_planner.generate(
        topic_name=module_start.topic.name,
        day_number=plan_day.day_number,
        total_days=module_start.module_plan.total_days,
        module_plan_day=plan_day,
        daily_hours_available=module_start.daily_hours_available,
        yesterday_completed=_extract_completed(yesterday_report),
        yesterday_pending=yesterday_pending,
    )

    daily_plan = DailyPlan(
        module_start_id=module_start.id,
        module_plan_day_id=plan_day.id,
        plan_date=today,
        tasks=ai_response.tasks,
        planned_hours=ai_response.planned_hours,
        status="pending",
        ai_raw_response=ai_response.model_dump(),
    )
    db.add(daily_plan)
    await db.commit()
    return daily_plan
```

Note the `(module_start_id, plan_date)` unique constraint from the schema — enforce this at the DB level so a race between the scheduler and the lazy-generation fallback can't create duplicate plans for the same day. Catch the unique-violation and just fetch-and-return the existing row instead of erroring.

---

## 6. Pipeline B — Check-in, Progress, Feedback, and Replanning

### 6.1 Progress extraction (Agent 5)

```python
# services/ai/progress_analyzer.py
async def analyze(daily_plan: DailyPlan, raw_text: str) -> ProgressAnalysisResponse:
    user_message = _build_progress_message(daily_plan.tasks, raw_text)
    raw_response = await call_claude(PROGRESS_ANALYZER_SYSTEM_PROMPT, user_message)
    return await validate_with_retry(raw_response, ProgressAnalysisResponse, ...)
```

### 6.2 Persisting study logs and updating topic state

```python
# services/daily_service.py
async def process_checkin(db, daily_plan: DailyPlan, raw_text: str) -> Feedback:
    analysis = await progress_analyzer.analyze(daily_plan, raw_text)

    report = DailyReport(
        daily_plan_id=daily_plan.id,
        raw_text=raw_text,
        completed_tasks=[t for t in analysis.task_results if t.status == "completed"],
        pending_tasks=[t for t in analysis.task_results if t.status != "completed"],
        actual_hours=analysis.actual_hours_spent,
        confidence_rating=analysis.confidence_rating,
        mood_note=analysis.mood_note,
        delay_reason=analysis.delay_reason,
    )
    db.add(report)
    await db.flush()

    for task_result in analysis.task_results:
        if task_result.status in ("completed", "partial"):
            topic_id = _resolve_topic_ref(task_result.task_ref, daily_plan)
            db.add(StudyLog(
                daily_report_id=report.id,
                topic_id=topic_id,
                units_completed=task_result.units_completed,
                status_change=task_result.status,
                logged_at=datetime.utcnow(),
            ))
            await topic_service.recalculate_completion(db, topic_id)  # reused from Module 1

    daily_plan.status = "completed" if _all_completed(analysis) else "partially_completed"
    await db.flush()

    # --- deterministic pace computation happens BEFORE calling the feedback agent ---
    pace_context = await _compute_pace_context(db, daily_plan.module_start_id)

    feedback_response = await feedback_generator.generate(
        daily_plan=daily_plan, analysis=analysis, pace_context=pace_context
    )

    feedback = Feedback(
        daily_report_id=report.id,
        exam_id=daily_plan.module_start.exam_id,
        performance_summary=feedback_response.performance_summary,
        risk_level=feedback_response.risk_level,
        pace_status=feedback_response.pace_status,
        suggestions=feedback_response.suggestions,
        motivational_note=feedback_response.motivational_note,
        ai_raw_response=feedback_response.model_dump(),
    )

    if feedback_response.adjustment_needed:
        adjustment_summary = await replanning_service.redistribute(
            db, daily_plan.module_start_id, pace_context
        )
        feedback.adjustments_made = adjustment_summary

    db.add(feedback)
    await db.commit()
    return feedback
```

**Critical point:** `pace_context` (days remaining, planned vs actual hours, completion delta) is computed by deterministic backend code and handed *into* the feedback agent as context — exactly the same principle from Module 1's difficulty estimator and Module 2's planner. The AI never computes pace or risk from scratch; it only interprets numbers you already trust.

### 6.3 Computing pace context (pure backend logic — no AI)

```python
# services/daily_service.py
async def _compute_pace_context(db, module_start_id: UUID) -> PaceContext:
    module_start = await module_service.get(db, module_start_id)
    plan_days = await module_plan_service.get_days(db, module_start.module_plan.id)

    days_elapsed = sum(1 for d in plan_days if d.status in ("completed", "adjusted"))
    days_total = len(plan_days)
    planned_hours_so_far = sum(d.planned_hours for d in plan_days if d.status == "completed")
    actual_hours_so_far = await study_log_service.sum_hours_for_module(db, module_start_id)

    exam = await exam_service.get(db, module_start.exam_id)
    days_remaining_exam = (exam.exam_date - date.today()).days if exam.exam_date else None
    overall_completion = await topic_service.get_exam_completion_pct(db, exam.id)

    return PaceContext(
        days_elapsed=days_elapsed,
        days_total=days_total,
        planned_hours_so_far=planned_hours_so_far,
        actual_hours_so_far=actual_hours_so_far,
        days_remaining_exam=days_remaining_exam,
        overall_completion_pct=overall_completion,
        current_streak_days=await streak_service.compute(db, module_start.exam_id),
    )
```

---

## 7. The Replanning Algorithm — Deterministic Design

This is the piece that most needs careful design rather than ad-hoc code, since it's the trickiest business logic in the whole app. Here's a concrete algorithm:

### 7.1 Inputs

- Remaining `module_plan_days` (status = `pending`, i.e. not yet reached)
- Total remaining *unallocated* subtopic work (subtopics not yet marked complete, with their `estimated_hours`)
- The hard constraint: **remaining days count must not exceed `days_remaining_exam`** (or the module's originally allocated window, whichever is the actual constraint you choose — configurable)
- Whether today's result was **ahead** or **behind** plan (`pace_status` from the feedback agent)

### 7.2 Case 1 — Student is ahead of plan

```python
async def _compress_schedule(db, module_start_id, remaining_days: list[ModulePlanDay]):
    incomplete_subtopics = await topic_service.get_incomplete_subtopics(db, module_start_id)
    total_remaining_hours = sum(t.estimated_hours for t in incomplete_subtopics)
    daily_hours = module_start.daily_hours_available

    ideal_days_needed = math.ceil(total_remaining_hours / daily_hours)

    if ideal_days_needed < len(remaining_days):
        days_saved = len(remaining_days) - ideal_days_needed
        # Reassign the saved days: default behavior = extend revision buffer at module end
        await _reallocate_days_to_revision(db, module_start_id, days_saved)
        # Redistribute remaining subtopics evenly across the now-shorter window
        await _redistribute_subtopics_across_days(
            db, remaining_days[:ideal_days_needed], incomplete_subtopics
        )
        # Mark the freed-up days as reclaimed (soft-delete or repurpose, don't hard-delete —
        # keep audit trail)
        for day in remaining_days[ideal_days_needed:]:
            day.status = "adjusted"
            day.focus_topics = []  # cleared, repurposed
        return f"Compressed module by {days_saved} day(s); added to revision buffer."
    return None
```

### 7.3 Case 2 — Student is behind plan

```python
async def _redistribute_behind(db, module_start_id, remaining_days: list[ModulePlanDay]):
    incomplete_subtopics = await topic_service.get_incomplete_subtopics(db, module_start_id)
    total_remaining_hours = sum(t.estimated_hours for t in incomplete_subtopics)
    daily_hours = module_start.daily_hours_available

    available_capacity = len(remaining_days) * daily_hours

    if total_remaining_hours <= available_capacity * 1.1:  # still fits within 10% tolerance
        # simple even redistribution across existing remaining days — no day count change
        await _redistribute_subtopics_across_days(db, remaining_days, incomplete_subtopics)
        return "Redistributed remaining topics across existing days — still on track."
    else:
        # doesn't fit: prioritize by weightage, defer/flag lowest-priority subtopics
        # rather than silently extending past the exam-date window
        sorted_subtopics = sorted(incomplete_subtopics, key=lambda t: t.weightage or 0, reverse=True)
        fitted, deferred = _fit_within_capacity(sorted_subtopics, available_capacity)
        await _redistribute_subtopics_across_days(db, remaining_days, fitted)
        return (
            f"Remaining workload exceeds available time by "
            f"{total_remaining_hours - available_capacity:.1f}h. "
            f"Prioritized higher-weightage topics: {[t.name for t in deferred]} "
            f"flagged as at-risk — consider increasing daily hours or extending the module."
        )
```

**This is the important design decision:** the algorithm **never silently pushes the module past the exam date**. If the math doesn't fit, it reprioritizes by weightage and *surfaces the conflict* in the message returned to the feedback layer (which the student sees), rather than quietly expanding the timeline. This mirrors exactly what you described originally — "it must fit in the initial planned days window" — and it's the kind of constraint that's much safer enforced in plain Python than hoped-for from an LLM prompt.

### 7.4 Redistribution helper

```python
def _redistribute_subtopics_across_days(days: list[ModulePlanDay], subtopics: list[Topic]):
    """Even distribution weighted by estimated_hours, respecting prerequisite order."""
    ordered = _topological_sort_by_prerequisite(subtopics)  # prereqs first
    hours_per_day = [d.planned_hours or module_start.daily_hours_available for d in days]

    day_idx = 0
    remaining_capacity = hours_per_day[0]
    for subtopic in ordered:
        hours_needed = subtopic.estimated_hours
        while hours_needed > 0 and day_idx < len(days):
            allocate = min(hours_needed, remaining_capacity)
            days[day_idx].focus_topics = days[day_idx].focus_topics + [subtopic.id]
            hours_needed -= allocate
            remaining_capacity -= allocate
            if remaining_capacity <= 0:
                day_idx += 1
                if day_idx < len(days):
                    remaining_capacity = hours_per_day[day_idx]
    for day in days:
        day.status = "adjusted"
```

This is intentionally simple (greedy bin-packing, not optimal scheduling) — a perfectly optimal packer isn't worth the complexity here. Respecting prerequisite order and staying within capacity is what actually matters for the feature to feel trustworthy.

### 7.5 Why this whole section is worth the extra code

If you let the Feedback Generator agent (Agent 6) *also* decide the specific new day-by-day breakdown, you'd need to feed it the entire remaining subtopic list, all their hours, all their prerequisites, on every single check-in — expensive, slow, and non-deterministic (same situation could produce different redistributions on different days, confusing the student who's trying to trust the plan). Keeping this as testable Python is what makes it debuggable and predictable — you can write unit tests with exact expected outputs, which you cannot meaningfully do against an LLM's free-form scheduling.

---

## 8. API Endpoints Summary

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/daily/today?module_start_id=` | Get (or lazily generate) today's plan |
| `POST` | `/daily/{daily_plan_id}/checkin` | Submit free-text end-of-day report, triggers Pipeline B |
| `GET` | `/daily/{daily_plan_id}/feedback` | Get feedback for a specific day |
| `GET` | `/exams/{id}/feedback-history` | List past feedback entries (for dashboard "see previous feedback") |
| `GET` | `/modules/{id}/daily-plans` | List all daily plans for a module (history view) |

---

## 9. Testing Strategy

- **`test_replanning_algorithm.py` deserves the most attention in this module.** Write table-driven tests: given a fixed set of remaining days, remaining subtopics with hours, and a pace scenario, assert the exact resulting day allocations. Include edge cases:
  - Student finishes everything early on the very last planned day (compress with 0 days to reallocate)
  - Student is so far behind that even prioritizing by weightage can't fit everything (assert `deferred` list is non-empty and message surfaces it)
  - Prerequisite ordering is respected even under compression
- **Mock the AI layer entirely** for pipeline tests — assert the orchestration (DB writes, rollup calls, conditional replanning trigger) is correct given a fixed `ProgressAnalysisResponse`/`FeedbackResponse` fixture, independent of actual model output quality.
- **Test the scheduler job's fault isolation** — one module's generation failure (mock a raised exception) shouldn't prevent other modules' plans from generating in the same batch run.
- **Test the unique constraint fallback** — simulate the lazy-generation endpoint racing with an already-existing `daily_plans` row for today, assert it returns the existing row rather than erroring.

---

## 10. Suggested Build Order Within Module 3

1. New models + migration for `daily_plans`, `daily_reports`, `study_logs`, `feedback`.
2. Daily Planner agent (Pipeline A) — build and test against a fixture master plan day + fake carry-over first.
3. `generate_daily_plan` + lazy-generation fallback endpoint — get "see today's tasks" working end-to-end before touching check-ins.
4. Progress Analyzer agent (Pipeline B, stage 1) — test against varied raw check-in text (vague, detailed, partial, off-topic).
5. `process_checkin` orchestration up through `study_logs` + rollup update — verify topic completion actually updates correctly before adding feedback.
6. `_compute_pace_context` — pure backend logic, test independently with fixture data.
7. Feedback Generator agent — wire in `pace_context`, verify tone/output against your own design intent (this is worth manually reading a dozen generated responses before moving on).
8. **The replanning algorithm** — build and test this thoroughly in isolation (section 7) before wiring it into the live pipeline.
9. Wire `adjustment_needed` → `replanning_service.redistribute` into `process_checkin`.
10. APScheduler setup + the daily batch job, with fault isolation.
11. Frontend: `TodayPage` (checklist + submit check-in), `CheckinPage`, `FeedbackHistoryPage`.
12. Full integration test: simulate several consecutive days (ahead one day, behind the next, on-track after) and assert the module's remaining days stay consistent and never exceed the exam-date constraint.

---

## 11. What NOT to Build Yet

- Weekly/monthly aggregated reviews, streak badges, consistency scores as their own analytics views (Module 4) — this module only needs `current_streak_days` as a *pace context input*, not a full analytics feature
- Spaced-repetition revision scheduling (Module 4)
- Confidence-based automatic revision-module creation (Module 4)
- Cross-module prioritization ("should I start DBMS or finish OS revision") — that's a Module 4 recommendation-engine concern
- Push notifications infrastructure — the `notifications` table can be written to now, but actual delivery (email/push) is a polish feature, not core to Module 3's function

The discipline here: Module 3 should make **one module's daily loop** (plan → do → report → feedback → adjust) rock solid and trustworthy before any cross-module or cross-time-period intelligence gets layered on in Module 4.
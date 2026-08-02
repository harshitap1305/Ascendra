# Module 1 — Exam Setup & Syllabus Engine
## Detailed Implementation Plan

Goal for this module: user can sign up, create an exam, paste a raw syllabus, have it parsed + enriched into a structured topic tree by AI, and browse/view it on a simple dashboard. Fully working end-to-end slice — no planning or daily mentor logic yet.

---

## 1. Tech Stack

| Layer | Choice | Why |
|---|---|---|
| Language | Python 3.11+ | async support, best AI SDK support |
| API framework | FastAPI | async-native, automatic OpenAPI docs, pydantic built in — pydantic models double as your JSON-schema validators for AI output |
| ORM | SQLAlchemy 2.0 (async) | mature, works cleanly with asyncpg, good migration story via Alembic |
| Migrations | Alembic | standard companion to SQLAlchemy |
| Database | PostgreSQL 15+ | JSONB support (needed for `ai_raw_response` columns), recursive CTEs (needed for topic tree) |
| DB driver | `asyncpg` | fastest async Postgres driver |
| Auth | `fastapi-users` or hand-rolled JWT with `python-jose` + `passlib[bcrypt]` | hand-rolled is fine for Module 1 scope, see below |
| AI SDK | `anthropic` Python SDK | structured JSON output, tool-use for schema enforcement |
| Validation | Pydantic v2 | already bundled with FastAPI, reuse same models for API I/O and AI response validation |
| Background tasks | FastAPI `BackgroundTasks` for now; upgrade to Celery + Redis only if enrichment starts taking too long synchronously | keep Module 1 simple; don't add infra you don't need yet |
| Frontend | React + Vite + TypeScript | fast dev loop, TS catches schema mismatches with backend early |
| Frontend state/data | TanStack Query (React Query) | handles async fetch/cache/loading states cleanly, pairs well with FastAPI |
| Frontend styling | Tailwind CSS | fast to build with, matches the "dashboard-heavy" nature of this app |
| Testing | `pytest` + `pytest-asyncio` + `httpx` (ASGI test client) | standard FastAPI testing stack |
| Env/config | `pydantic-settings` | typed env var loading |

### Python dependencies (`requirements.txt` / `pyproject.toml`)

```
fastapi
uvicorn[standard]
sqlalchemy[asyncio]>=2.0
asyncpg
alembic
pydantic
pydantic-settings
python-jose[cryptography]
passlib[bcrypt]
python-multipart
anthropic
tenacity
python-dotenv
pytest
pytest-asyncio
httpx
```

`tenacity` is worth calling out — you'll use it to wrap every AI call with retry-on-failure logic (network errors, transient API errors), separate from your JSON-validation-retry logic.

### Frontend dependencies

```
react, react-dom, react-router-dom
@tanstack/react-query
axios
tailwindcss
zod                # validate/type API responses on frontend too
react-hook-form    # for the exam creation form
```

---

## 2. Project Structure

```
backend/
  app/
    main.py                  # FastAPI app instantiation, router registration
    config.py                 # pydantic-settings, reads .env
    database.py                # async engine, session factory, get_db dependency
    models/
      user.py
      exam.py
      topic.py
      resource.py
      raw_syllabus.py
      ai_interaction.py
    schemas/                   # Pydantic request/response models
      user.py
      exam.py
      topic.py
      auth.py
      ai_syllabus.py           # schemas matching the AI prompt JSON contracts
    api/
      deps.py                  # get_current_user, get_db, pagination helpers
      routes/
        auth.py
        exams.py
        topics.py
        syllabus.py             # upload + parse + enrich endpoints
    services/
      auth_service.py
      exam_service.py
      topic_service.py           # tree building, rollup logic
      ai/
        client.py                # thin wrapper around anthropic SDK
        syllabus_parser.py        # agent 1 logic
        difficulty_estimator.py   # agent 2 logic
        prompts/
          syllabus_parser.txt
          difficulty_estimator.txt
    core/
      security.py               # password hashing, JWT encode/decode
      exceptions.py              # custom exception classes -> HTTP error mapping
    alembic/
      versions/
    tests/
      test_auth.py
      test_exams.py
      test_syllabus_parsing.py
  alembic.ini
  pyproject.toml
  .env.example

frontend/
  src/
    api/
      client.ts                 # axios instance with interceptors (auth header, error handling)
      auth.ts
      exams.ts
      topics.ts
    pages/
      LoginPage.tsx
      SignupPage.tsx
      ExamListPage.tsx
      ExamCreatePage.tsx
      SyllabusUploadPage.tsx
      SyllabusReviewPage.tsx       # shows parsed tree before final save, allows edits
      ExamDashboardPage.tsx
    components/
      TopicTree.tsx
      ProgressBar.tsx
      ExamCard.tsx
    hooks/
      useAuth.ts
      useExams.ts
    types/
      index.ts                    # shared TS types mirroring backend schemas
```

Why this layered structure (`api` → `services` → `models`): keeps route handlers thin (parse request, call service, return response). All business logic — including AI orchestration — lives in `services/`, which makes it testable without spinning up HTTP.

---

## 3. Features & Implementation Details

### 3.1 Authentication

**Keep it simple for Module 1** — hand-rolled JWT is enough; don't reach for `fastapi-users` yet, it adds abstraction you don't need at this stage.

- `POST /auth/signup` — hash password with `passlib` (bcrypt), create `users` row, return JWT.
- `POST /auth/login` — verify password, return JWT (access token; skip refresh tokens for now — revisit if you add mobile clients later).
- `GET /auth/me` — protected route, returns current user, used by frontend to check session on load.

**Implementation notes:**
- Store JWT secret in env, never hardcode.
- Token payload: `{ sub: user_id, exp }`. Keep it minimal — don't stuff user data into the token; fetch fresh from DB when needed.
- `deps.py` → `get_current_user(token: str = Depends(oauth2_scheme), db = Depends(get_db))` decodes JWT, loads user, raises 401 if invalid/expired. Every protected route depends on this.
- Frontend stores token in memory + `localStorage` (fine for this use case), attaches via axios interceptor.

### 3.2 Exam CRUD

- `POST /exams` — create exam (name, description, exam_date, target_finish_date, daily_study_hours, experience_level, goal_score).
- `GET /exams` — list current user's exams (filter by status).
- `GET /exams/{id}` — single exam detail.
- `PATCH /exams/{id}` — update fields (e.g. change daily_study_hours later).
- `DELETE /exams/{id}` — soft delete (set `status = archived`, don't hard-delete — you'll want this data for analytics eventually).

**Implementation notes:**
- Pydantic schema `ExamCreate` should validate `exam_date` is in the future if provided (a simple `field_validator`).
- Ownership check: every `GET/PATCH/DELETE /exams/{id}` must verify `exam.user_id == current_user.id`, else 404 (not 403 — don't leak existence of other users' resources).

### 3.3 Syllabus Upload & Parsing (the core AI feature of this module)

This is the most important part to get right. Break it into three explicit steps rather than one big "upload and magically get a tree" endpoint — you want each step inspectable and retryable.

**Step A — Save raw text**

`POST /exams/{id}/syllabus` — body: `{ raw_text: string }`
- Creates a `raw_syllabus_uploads` row with `parsed_status = 'pending'`.
- Returns the upload id immediately.

**Step B — Trigger parsing (agent 1)**

`POST /syllabus-uploads/{id}/parse`
- Loads the raw text, calls `syllabus_parser` service.
- Service builds the prompt from the template, calls the AI client, validates response against the Pydantic schema mirroring the JSON schema from the prompt doc.
- On success: recursively walk the returned tree and insert into `topics` (compute `depth`, `parent_id`, `order_index`, `is_leaf`). Wrap all inserts in a single DB transaction — if any node fails, roll back the whole tree rather than leaving a half-built syllabus.
- On failure: retry once with the validation error appended to the prompt (see Implementation Notes in the prompt doc). If it fails again, set `parsed_status = 'failed'` and return a clear error — **do not silently save partial garbage.**
- Update `raw_syllabus_uploads.parsed_status = 'success'`.

**Step C — Review & edit before finalizing**

This step matters a lot in practice — AI parsing won't be 100% right, especially on messy pasted text, and users need a chance to fix it before it's "locked in."

- `GET /exams/{id}/topics` — returns the full tree (see 3.4) for review.
- `PATCH /topics/{id}` — rename, move (change `parent_id`), delete, reorder — lets the user fix AI mistakes inline.
- Frontend: `SyllabusReviewPage` shows the tree as an editable outline (indent = depth) before the user clicks "Looks good."

**Step D — Trigger enrichment (agent 2)**

`POST /exams/{id}/enrich-topics`
- Runs after the user confirms the tree is correct (don't run this automatically right after parsing — enrichment is more expensive and the tree might still change).
- Because syllabi can be large, **chunk by top-level topic**: fetch each root topic + its full subtree, call the difficulty estimator per chunk, not the whole exam in one call.
- Run chunks concurrently with `asyncio.gather` (bounded — e.g. `asyncio.Semaphore(3)` so you don't blow past API rate limits), not sequentially, to keep this fast even for large syllabi.
- Resolve `prerequisite_topic_name` → `prerequisite_topic_id` by matching against topic names within the same exam. If no confident match, leave null rather than guessing.
- Update each topic row with `difficulty`, `estimated_hours`, `weightage` (only if it was null), `prerequisite_topic_id`.

**Why split parse and enrich into separate user-triggered steps instead of one pipeline:** enrichment cost/latency scales with syllabus size, and you don't want a user's very first interaction with the app to be a 30-second blocking wait with no visibility. Splitting also means if parsing looks wrong, they fix it before you spend AI calls enriching the wrong tree.

### 3.4 Topic Tree Retrieval & Rollup

`GET /exams/{id}/topics` — return the full nested tree in one call (don't make the frontend do N+1 requests).

**Implementation:** use a recursive CTE to fetch all topics for an exam in one query, then build the nested structure in Python (simpler and more testable than nesting logic in raw SQL):

```sql
WITH RECURSIVE topic_tree AS (
    SELECT * FROM topics WHERE exam_id = :exam_id AND parent_id IS NULL
    UNION ALL
    SELECT t.* FROM topics t
    INNER JOIN topic_tree tt ON t.parent_id = tt.id
)
SELECT * FROM topic_tree ORDER BY depth, order_index;
```

Then in Python, build a `dict[id -> node]` and attach children to parents in a single pass (O(n), no repeated lookups).

**Completion rollup** (you'll need this working even though real progress tracking is Module 3): write a `recalculate_completion(topic_id)` function in `topic_service.py` that:
- For leaf topics: completion comes directly from `study_logs` (Module 3) — for now, defaults to 0.
- For parent topics: `completion_pct = weighted average of children's completion_pct`, weighted by each child's `estimated_hours` (falls back to equal weighting if `estimated_hours` is null).

Build this now even though nothing calls it yet — it means Module 3 just has to call this function after logging progress, not design the rollup logic from scratch under time pressure later.

### 3.5 Resources (exam-level, optional in this module)

Minimal version for Module 1 — full resource parsing happens in Module 2:
- `POST /exams/{id}/resources` — manually add a resource (title, type, url).
- `GET /exams/{id}/resources` — list.

Keep this thin; don't build AI resource-parsing yet, that's explicitly Module 2 scope.

### 3.6 Dashboard (simple version)

`GET /exams/{id}/summary` — single aggregate endpoint, computed via SQL (not by walking the tree in Python on every request):

```sql
SELECT
  COUNT(*) FILTER (WHERE is_leaf) AS total_leaf_topics,
  COUNT(*) FILTER (WHERE is_leaf AND status = 'completed') AS completed_leaf_topics
FROM topics WHERE exam_id = :exam_id;
```

Returns `{ total_topics, completed_topics, progress_pct }`. Frontend renders this as a simple progress bar + counts on `ExamDashboardPage`. Don't overbuild this yet — full analytics is Module 4.

---

## 4. AI Integration — Concrete Implementation Pattern

This is the part worth being most careful about. Here's the concrete pattern to follow for both agents in this module:

```python
# services/ai/client.py
from anthropic import AsyncAnthropic
from tenacity import retry, stop_after_attempt, wait_exponential

client = AsyncAnthropic()  # reads ANTHROPIC_API_KEY from env

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
async def call_claude(system: str, user_message: str, model: str = "claude-sonnet-4-6") -> str:
    response = await client.messages.create(
        model=model,
        max_tokens=4096,
        system=system,
        messages=[{"role": "user", "content": user_message}],
    )
    return response.content[0].text
```

```python
# services/ai/syllabus_parser.py
import json
from pydantic import ValidationError
from app.schemas.ai_syllabus import ParsedSyllabusResponse
from .client import call_claude

SYSTEM_PROMPT = open("services/ai/prompts/syllabus_parser.txt").read()

async def parse_syllabus(exam_name: str, raw_text: str) -> ParsedSyllabusResponse:
    user_message = f"Exam: {exam_name}\nRaw syllabus text:\n\"\"\"\n{raw_text}\n\"\"\""

    raw_response = await call_claude(SYSTEM_PROMPT, user_message)

    try:
        data = json.loads(raw_response)
        return ParsedSyllabusResponse.model_validate(data)
    except (json.JSONDecodeError, ValidationError) as e:
        # one retry with the error fed back in
        retry_message = f"{user_message}\n\nYour previous response failed validation: {e}\nReturn corrected JSON only."
        raw_response = await call_claude(SYSTEM_PROMPT, retry_message)
        data = json.loads(raw_response)
        return ParsedSyllabusResponse.model_validate(data)  # let this raise if it fails again
```

Key points this pattern captures:
- **Pydantic model = the JSON schema.** Define `ParsedSyllabusResponse` once in `schemas/ai_syllabus.py`, matching the schema from the prompt doc exactly — this is your validation layer, not a separate JSON Schema file.
- **`tenacity` retry** handles transient network/API failures (agent 1 layer).
- **Manual retry-with-error-feedback** handles the AI returning malformed/invalid JSON (agent 2 layer) — these are different failure modes and deserve different handling.
- **System prompts live in `.txt` files**, not inline strings — makes them easy to iterate on without touching code, and easy to diff in git.
- Always log to `ai_interactions` — wrap the above in a decorator or context manager that captures `input_payload`, `output_payload`, `latency_ms`, and `status`, so you're not repeating this logging in every agent function.

```python
# services/ai/logging_wrapper.py
import time
from app.models.ai_interaction import AIInteraction

async def log_ai_call(db, user_id, exam_id, agent_type, input_payload, fn, *args, **kwargs):
    start = time.monotonic()
    status = "success"
    output_payload = None
    try:
        result = await fn(*args, **kwargs)
        output_payload = result.model_dump() if hasattr(result, "model_dump") else result
        return result
    except Exception:
        status = "failed"
        raise
    finally:
        latency_ms = int((time.monotonic() - start) * 1000)
        db.add(AIInteraction(
            user_id=user_id, exam_id=exam_id, agent_type=agent_type,
            input_payload=input_payload, output_payload=output_payload,
            latency_ms=latency_ms, status=status,
        ))
        await db.commit()
```

Use this wrapper around every AI service call site, not just these two — it pays off across all 7 agents later.

---

## 5. Performance & Correctness Considerations

**Database:**
- Add indexes exactly as specified in the schema doc: `(exam_id, parent_id)` and `(exam_id, status)` on `topics` — the tree fetch and dashboard summary both depend on these.
- Use a single transaction for the whole "insert parsed tree" operation — partial trees are worse than no tree.
- Use `async` SQLAlchemy sessions throughout — don't mix sync and async DB calls, it's a common source of subtle bugs with FastAPI.

**AI calls:**
- Bound concurrency with a semaphore when enriching multiple topic chunks — protects you from rate limits and from one exam's parsing hogging all your API quota if multiple users hit "enrich" at once.
- Set `max_tokens` generously enough for large topic trees but capped — if a syllabus is enormous, chunk it rather than raising the limit indefinitely.
- Cache nothing yet in Module 1 — parsing/enrichment happen once per exam, caching isn't the bottleneck here. Don't over-engineer.

**API design:**
- Return the *full* topic tree in one response for `GET /exams/{id}/topics` rather than paginating — trees are awkward to paginate and syllabi are small enough (hundreds of nodes, not millions) that this is fine.
- Make parse/enrich endpoints return quickly with a status the frontend can poll, OR use FastAPI `BackgroundTasks` + a `GET /syllabus-uploads/{id}/status` endpoint the frontend polls every 2s while showing a loading state. Don't block the HTTP request for 10-30 seconds — bad UX and risks gateway timeouts.

**Error handling:**
- Centralize exception → HTTP status mapping in `core/exceptions.py` (e.g. `NotFoundError` → 404, `AIParsingFailedError` → 422 with a clear message) so route handlers stay clean and error responses stay consistent across the whole app.

---

## 6. Suggested Build Order Within Module 1

1. Project scaffolding: FastAPI app, DB connection, Alembic setup, `.env` config.
2. `users` table + auth endpoints (signup/login/me) — test with `httpx` before moving on.
3. `exams` table + CRUD endpoints.
4. `raw_syllabus_uploads` + `topics` tables.
5. Syllabus parser service (agent 1) — build and test against a few real messy syllabus pastes early, this is where prompt iteration happens.
6. Topic tree insert logic (recursive insert + recursive CTE fetch) — test tree correctness independently of the AI call (feed it a fixed JSON fixture).
7. Topic review/edit endpoints (`PATCH /topics/{id}`).
8. Difficulty estimator service (agent 2) — chunking + concurrency.
9. Dashboard summary endpoint.
10. Frontend: auth pages → exam creation → syllabus paste/review UI → dashboard.
11. Write tests for: tree building from a fixed fixture, rollup calculation, auth flows, ownership checks (user A can't access user B's exam).

This order front-loads the riskiest part (AI parsing reliability) so you find prompt/schema problems early rather than after building the whole UI around an assumption that turns out wrong.

---

## 7. What NOT to Build Yet (explicitly out of scope for Module 1)

- Resource AI-parsing (Module 2)
- Any planning/day generation logic (Module 2)
- Daily check-ins, feedback (Module 3)
- Weekly/monthly analytics, revision engine, confidence tracking (Module 4)
- Celery/Redis background job infra — FastAPI `BackgroundTasks` is enough at this scale
- Refresh tokens / OAuth login — plain JWT is enough until you have a real reason to add these

Keeping this boundary strict is what lets you actually ship Module 1 as a working, demoable product before moving on.

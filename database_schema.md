# Database Schema — AI Exam Preparation Mentor

PostgreSQL. Organized by module. Every table includes `created_at` / `updated_at` unless noted. UUIDs used as primary keys throughout for simplicity across services.

---

## MODULE 1 — Exam Setup & Syllabus Engine

### `users`
| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| name | VARCHAR(120) | |
| email | VARCHAR(255) UNIQUE | |
| password_hash | VARCHAR(255) | |
| timezone | VARCHAR(50) | default 'Asia/Kolkata' |
| created_at | TIMESTAMPTZ | |
| updated_at | TIMESTAMPTZ | |

### `exams`
One user can prepare for multiple exams (GATE + ESE simultaneously, for example).

| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| user_id | UUID FK → users.id | |
| name | VARCHAR(150) | e.g. "GATE CS 2027" |
| description | TEXT | nullable |
| exam_date | DATE | nullable — approximate ok |
| target_finish_date | DATE | user's own prep-completion goal, may differ from exam_date |
| daily_study_hours | NUMERIC(4,2) | default availability, editable later |
| experience_level | VARCHAR(20) | enum: beginner / intermediate / revision |
| goal_score | VARCHAR(100) | free text, e.g. "AIR under 500" |
| status | VARCHAR(20) | enum: active / paused / completed / archived |
| created_at | TIMESTAMPTZ | |
| updated_at | TIMESTAMPTZ | |

> **Index:** `(user_id, status)` — dashboard always filters active exams per user.

### `topics`
Self-referencing tree — handles topic → subtopic → sub-subtopic with unlimited depth, so you don't need separate tables for each level.

| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| exam_id | UUID FK → exams.id | |
| parent_id | UUID FK → topics.id | NULL for root topics |
| name | VARCHAR(255) | |
| depth | SMALLINT | 0 = topic, 1 = subtopic, 2 = sub-subtopic — denormalized for fast querying |
| order_index | INT | preserves syllabus order as pasted |
| difficulty | VARCHAR(10) | enum: low / medium / high — AI generated |
| weightage | NUMERIC(5,2) | nullable, either user-given or AI-estimated, % of exam |
| estimated_hours | NUMERIC(6,2) | AI generated |
| prerequisite_topic_id | UUID FK → topics.id | nullable, self-referencing |
| status | VARCHAR(20) | enum: not_started / in_progress / completed / skipped |
| completion_pct | NUMERIC(5,2) | default 0, updated by Progress Service |
| is_leaf | BOOLEAN | true if no children — only leaf topics get marked "complete" directly; parents roll up |
| created_at | TIMESTAMPTZ | |
| updated_at | TIMESTAMPTZ | |

> **Index:** `(exam_id, parent_id)`, `(exam_id, status)`
> **Constraint:** prevent `prerequisite_topic_id = id`

Why self-referencing instead of fixed `topic/subtopic/subsubtopic` tables: syllabi are inconsistently nested (some exams give you 2 levels, some give you 4). A recursive tree avoids schema changes later. Use a recursive CTE to fetch full trees or rollup completion.

### `raw_syllabus_uploads`
Keep the original pasted text — useful for re-parsing if AI structuring was imperfect, and for audit/debugging.

| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| exam_id | UUID FK → exams.id | |
| raw_text | TEXT | |
| parsed_status | VARCHAR(20) | pending / success / failed |
| ai_model_used | VARCHAR(50) | |
| created_at | TIMESTAMPTZ | |

### `resources`
Generic table for videos/books/PYQ-sets etc., usable both at exam-wide level and inside a specific module plan (Module 2).

| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| exam_id | UUID FK → exams.id | |
| topic_id | UUID FK → topics.id | nullable — resource may be topic-specific or general |
| type | VARCHAR(20) | enum: video / book / website / pyq / notes / other |
| title | VARCHAR(255) | |
| source_name | VARCHAR(150) | e.g. "Gate Smashers", "Galvin" |
| url | TEXT | nullable |
| total_units | INT | nullable — e.g. total videos in playlist, total pages |
| created_at | TIMESTAMPTZ | |

---

## MODULE 2 — Module Planner

### `module_starts`
Represents the raw input when a user starts working on a given topic (a "module" in your terminology = one topic/chapter).

| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| topic_id | UUID FK → topics.id | the chapter being started |
| exam_id | UUID FK → exams.id | denormalized for query convenience |
| raw_input | TEXT | user's free-text dump of resources/plan intent |
| expected_hours | NUMERIC(6,2) | nullable, user-given |
| daily_hours_available | NUMERIC(4,2) | can override exam default for this module |
| started_at | TIMESTAMPTZ | |
| status | VARCHAR(20) | enum: planning / active / completed / abandoned |

### `module_plans`
The AI-generated **master plan** — day-by-day breakdown, generated once, rarely regenerated wholesale.

| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| module_start_id | UUID FK → module_starts.id | |
| total_days | INT | |
| ai_raw_response | JSONB | full AI output stored for audit/debug |
| generated_at | TIMESTAMPTZ | |
| regenerated_count | INT | default 0 — track how many times master plan was recalculated |

### `module_plan_days`
Each row = one planned day inside a module's master plan (this is the "Day 1: Processes, 2 days" breakdown).

| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| module_plan_id | UUID FK → module_plans.id | |
| day_number | INT | 1-indexed, relative to module start |
| planned_date | DATE | nullable — can be computed or fixed |
| focus_topics | JSONB | array of topic_ids / sub-focus areas planned for that day |
| planned_hours | NUMERIC(4,2) | |
| status | VARCHAR(20) | enum: pending / active / completed / adjusted |

### `module_resources`
Links parsed resources (videos, books, etc.) to a specific module start, with structured progress tracking.

| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| module_start_id | UUID FK → module_starts.id | |
| resource_id | UUID FK → resources.id | |
| units_planned | INT | e.g. "12 videos" |
| units_completed | INT | default 0 |

---

## MODULE 3 — Daily Mentor

### `daily_plans`
The actual day's task list — generated fresh each morning from `module_plan_days` + yesterday's carry-over.

| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| module_start_id | UUID FK → module_starts.id | |
| module_plan_day_id | UUID FK → module_plan_days.id | nullable — links back to master plan day it derives from |
| plan_date | DATE | |
| tasks | JSONB | array of `{ description, topic_id, type, target_units }` |
| planned_hours | NUMERIC(4,2) | |
| status | VARCHAR(20) | enum: pending / in_progress / completed / partially_completed |
| ai_raw_response | JSONB | |
| created_at | TIMESTAMPTZ | |

> **Index:** `(module_start_id, plan_date)` UNIQUE — one plan per module per day.

### `daily_reports`
The end-of-day check-in — raw user text + AI-extracted structured result.

| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| daily_plan_id | UUID FK → daily_plans.id | |
| raw_text | TEXT | what the user typed |
| completed_tasks | JSONB | AI-extracted list matched against planned tasks |
| pending_tasks | JSONB | |
| actual_hours | NUMERIC(4,2) | nullable, AI-extracted or user-given |
| confidence_rating | SMALLINT | nullable, 1–5, user self-rated |
| mood_note | TEXT | nullable, e.g. "had headache" |
| delay_reason | TEXT | nullable, AI-extracted |
| submitted_at | TIMESTAMPTZ | |

### `study_logs`
Granular, append-only log of actual topic-level progress — this is what feeds `topics.completion_pct` rollups and all analytics. Kept separate from `daily_reports` because one report can touch multiple topics.

| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| daily_report_id | UUID FK → daily_reports.id | |
| topic_id | UUID FK → topics.id | |
| hours_spent | NUMERIC(4,2) | nullable |
| units_completed | INT | nullable, e.g. videos watched, questions solved |
| status_change | VARCHAR(20) | e.g. moved to "completed" |
| logged_at | TIMESTAMPTZ | |

### `feedback`
AI mentor's response after each check-in — kept as its own table so it's easy to list "past feedback" in the dashboard.

| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| daily_report_id | UUID FK → daily_reports.id | |
| exam_id | UUID FK → exams.id | denormalized, for quick listing |
| performance_summary | TEXT | |
| risk_level | VARCHAR(10) | enum: low / medium / high |
| pace_status | VARCHAR(20) | enum: ahead / on_track / behind |
| adjustments_made | JSONB | nullable — e.g. which future days were compressed/expanded |
| suggestions | TEXT | |
| motivational_note | TEXT | |
| ai_raw_response | JSONB | |
| created_at | TIMESTAMPTZ | |

---

## MODULE 4 — Analytics & AI Coach

### `weekly_reviews`
| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| exam_id | UUID FK → exams.id | |
| week_start_date | DATE | |
| week_end_date | DATE | |
| planned_hours | NUMERIC(6,2) | |
| actual_hours | NUMERIC(6,2) | |
| topics_completed | INT | |
| skipped_days | INT | |
| avg_productivity_pct | NUMERIC(5,2) | |
| strong_topics | JSONB | array of topic_ids |
| weak_topics | JSONB | array of topic_ids |
| ai_summary | TEXT | |
| ai_raw_response | JSONB | |
| generated_at | TIMESTAMPTZ | |

> **Index:** `(exam_id, week_start_date)` UNIQUE

### `monthly_reviews`
Same shape as weekly, at month grain, plus prediction fields.

| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| exam_id | UUID FK → exams.id | |
| month | DATE | first-of-month marker |
| coverage_pct | NUMERIC(5,2) | |
| expected_coverage_pct | NUMERIC(5,2) | |
| avg_daily_hours | NUMERIC(4,2) | |
| missed_days | INT | |
| weakest_topic_id | UUID FK → topics.id | nullable |
| strongest_topic_id | UUID FK → topics.id | nullable |
| projected_completion_date | DATE | nullable |
| required_daily_hours | NUMERIC(4,2) | nullable — recalculated pace needed to hit exam date |
| ai_summary | TEXT | |
| ai_raw_response | JSONB | |
| generated_at | TIMESTAMPTZ | |

### `revision_schedule`
Auto-generated spaced-repetition entries per topic.

| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| topic_id | UUID FK → topics.id | |
| exam_id | UUID FK → exams.id | denormalized |
| revision_number | SMALLINT | 1st, 2nd, 3rd revision... |
| scheduled_date | DATE | |
| status | VARCHAR(20) | enum: pending / done / skipped / rescheduled |
| trigger_reason | VARCHAR(30) | enum: spaced_repetition / low_confidence / manual |
| completed_at | TIMESTAMPTZ | nullable |
| created_at | TIMESTAMPTZ | |

> **Index:** `(exam_id, scheduled_date, status)` — used to build "today's revision queue"

### `confidence_logs`
Tracks self-rated confidence over time per topic (not just once) — lets you see if confidence improves across revisions.

| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| topic_id | UUID FK → topics.id | |
| rating | SMALLINT | 1–5 |
| context | VARCHAR(30) | enum: module_complete / post_revision / manual |
| logged_at | TIMESTAMPTZ | |

---

## Supporting / Cross-Cutting Tables

### `ai_interactions`
Log every AI call for debugging, cost tracking, and prompt-quality iteration. Non-negotiable — you will need this once the AI misbehaves and you need to see what context it was given.

| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| user_id | UUID FK → users.id | |
| exam_id | UUID FK → exams.id | nullable |
| agent_type | VARCHAR(30) | enum: syllabus_parser / difficulty_estimator / planner / daily_planner / progress_analyzer / feedback_generator / analytics_agent |
| input_payload | JSONB | exact context sent |
| output_payload | JSONB | raw AI response |
| model_used | VARCHAR(50) | |
| latency_ms | INT | nullable |
| token_count | INT | nullable |
| status | VARCHAR(20) | success / failed / retried |
| created_at | TIMESTAMPTZ | |

### `notifications` (optional, for the "proactive morning/evening message" feature)
| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| user_id | UUID FK → users.id | |
| exam_id | UUID FK → exams.id | |
| type | VARCHAR(20) | enum: morning_brief / evening_nudge / risk_alert |
| message | TEXT | |
| is_read | BOOLEAN | default false |
| created_at | TIMESTAMPTZ | |

---

## Key Design Decisions Explained

**1. Recursive `topics` table, not fixed levels.**
Real syllabi don't respect neat 2 or 3-level hierarchies. A self-referencing tree with a `depth` column handles this cleanly and lets you write one recursive CTE for "give me the full tree" or "roll up completion % from leaves to root."

**2. `completion_pct` is denormalized on `topics`, but the source of truth is `study_logs`.**
Never let the frontend or AI write directly to `topics.completion_pct`. A backend job (triggered after every `study_logs` insert) recalculates: leaf topics get % from logged units vs. estimated units; parent topics get the weighted average of children's %. This keeps rollups consistent no matter which path updated progress.

**3. Master plan (`module_plans` / `module_plan_days`) is separate from daily execution (`daily_plans`).**
This is the "don't let AI replan everything from scratch every day" principle from your design. The master plan is the stable skeleton; `daily_plans` are generated against it and can adjust future *unstarted* days without touching the overall day budget. `module_plan_days.status = 'adjusted'` flags when redistribution happened.

**4. Every AI JSON response is stored raw (`ai_raw_response` JSONB columns + `ai_interactions`).**
You will change your prompts constantly during development. Keeping raw responses means you can re-derive structured fields later without re-calling the AI, and you can audit exactly why a plan looks the way it does.

**5. `daily_reports` vs `study_logs` are separate.**
One evening check-in (`daily_reports`) can report progress across multiple topics — e.g. "watched a Process video and did some Deadlock PYQs." `study_logs` breaks that single report into one row per topic touched, which is what your analytics and rollups actually query against.

**6. Revision and confidence are their own tables, not columns on `topics`.**
A topic gets revised multiple times over months (1 day, 3 days, 7 days, 30 days later). Modeling this as rows, not columns, means you don't hit a wall when you want a 5th revision cycle, and you can query "what's due today" trivially.

---

## Suggested Build Order (matches your 4 modules)

1. `users`, `exams`, `topics`, `raw_syllabus_uploads`, `resources` → Module 1
2. `module_starts`, `module_plans`, `module_plan_days`, `module_resources` → Module 2
3. `daily_plans`, `daily_reports`, `study_logs`, `feedback` → Module 3
4. `weekly_reviews`, `monthly_reviews`, `revision_schedule`, `confidence_logs` → Module 4
5. `ai_interactions`, `notifications` → build alongside Module 1, used throughout

This lets each module's tables ship independently, matching the incremental build plan we laid out earlier.

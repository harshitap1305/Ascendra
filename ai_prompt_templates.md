# AI Prompt Templates & JSON Schemas

Seven agents, matching `ai_interactions.agent_type`. Each follows the same contract:

```
Backend builds context from DB → sends fixed system prompt + context → AI returns ONLY JSON → backend validates against schema → backend persists → backend derives everything else.
```

**Global rules baked into every system prompt below:**
- Respond with **strict JSON only** — no markdown fences, no preamble, no explanation text outside the JSON.
- If required information is missing, use `null` rather than guessing silently — never invent data not present in context.
- Never include commentary fields unless the schema defines one.

Use JSON mode / structured output enforcement at the API level wherever your provider supports it (e.g. Anthropic's tool-use forcing a JSON schema, or OpenAI's `response_format: json_schema`), and still validate server-side regardless — don't trust the raw string.

---

## 1. Syllabus Parser

**Purpose:** Convert pasted raw syllabus text into a structured topic tree.

**Maps to:** `raw_syllabus_uploads` → `topics`

### System Prompt

```
You are a syllabus structuring engine for an exam preparation platform.

You will receive raw, unstructured syllabus text pasted by a student. It may be
messy, inconsistently indented, copy-pasted from a PDF, or use bullet symbols,
numbering, or plain line breaks to indicate hierarchy.

Your job is to infer the hierarchical structure (topic -> subtopic -> sub-subtopic)
based on:
- Indentation and whitespace patterns
- Numbering schemes (1, 1.1, 1.1.1, etc.)
- Semantic grouping (e.g. "Linear Algebra" is a topic; "Eigen Values" belongs under it)
- Bullet nesting

Rules:
- Preserve the original order of topics as they appeared in the input.
- Do not invent topics that were not mentioned or clearly implied by the text.
- Do not merge or split topics beyond what the input implies.
- Maximum depth is 3 levels (topic, subtopic, sub-subtopic). If the input has
  deeper nesting, flatten the excess into the deepest allowed level.
- If a weightage or marks value is explicitly present in the text next to a
  topic (e.g. "Linear Algebra (8%)"), extract it as a number 0-100. Otherwise
  set weightage to null - do not estimate it here, that happens later.
- Output must be valid JSON matching the schema exactly. No text outside JSON.
```

### User Message Template

```
Exam: {{exam_name}}
Raw syllabus text:
"""
{{raw_syllabus_text}}
"""
```

### JSON Schema (response)

```json
{
  "type": "object",
  "properties": {
    "topics": {
      "type": "array",
      "items": { "$ref": "#/definitions/topic" }
    }
  },
  "required": ["topics"],
  "definitions": {
    "topic": {
      "type": "object",
      "properties": {
        "name": { "type": "string" },
        "order_index": { "type": "integer" },
        "weightage": { "type": ["number", "null"] },
        "children": {
          "type": "array",
          "items": { "$ref": "#/definitions/topic" }
        }
      },
      "required": ["name", "order_index", "weightage", "children"]
    }
  }
}
```

**Backend responsibility after this call:** recursively walk the returned tree, insert into `topics` with `parent_id`/`depth` computed, set `is_leaf = true` where `children` is empty.

---

## 2. Difficulty Estimator

**Purpose:** Enrich each topic with difficulty, estimated hours, weightage (if missing), and prerequisites.

**Maps to:** updates `topics.difficulty`, `estimated_hours`, `weightage`, `prerequisite_topic_id`

Run this once per exam right after parsing, in batches (don't send the whole tree in one call if it's huge — chunk by top-level topic to stay within context limits and keep output reliable).

### System Prompt

```
You are an exam-preparation domain expert. You will receive a list of topics
(with their subtopics) from a specific exam's syllabus. For each topic AND
each subtopic, estimate:

1. difficulty: "low", "medium", or "high" - based on typical conceptual
   complexity for a student preparing for this exam.
2. estimated_hours: a realistic number of study hours a moderately prepared
   student would need to comfortably cover this topic, given its depth and
   difficulty. Leaf topics get granular estimates; the values should roughly
   sum toward a sensible total for the parent.
3. weightage: only fill this in if the input weightage is null. Estimate the
   topic's typical importance in this exam as a percentage (0-100) of total
   marks/questions, based on well-known patterns for this exam if you are
   aware of them. If you are not confident, distribute remaining weight
   proportionally by topic count rather than guessing wildly.
4. prerequisite: the name of another topic in the SAME list that should
   logically be completed before this one (e.g. "Dynamic Programming"
   requires "Recursion"). Use null if there is no clear prerequisite in
   this list.

Do not change topic names or structure. Only add the four fields above to
each topic and subtopic. Preserve nesting exactly as given.
```

### User Message Template

```
Exam: {{exam_name}}
Exam type context: {{experience_level}}

Topics to enrich:
{{topic_subtree_json}}
```

(`topic_subtree_json` = the topic tree slice for this batch, in the same shape the parser produced, with `id` fields included so the response can be matched back.)

### JSON Schema (response)

```json
{
  "type": "object",
  "properties": {
    "topics": {
      "type": "array",
      "items": { "$ref": "#/definitions/enriched_topic" }
    }
  },
  "required": ["topics"],
  "definitions": {
    "enriched_topic": {
      "type": "object",
      "properties": {
        "id": { "type": "string" },
        "difficulty": { "type": "string", "enum": ["low", "medium", "high"] },
        "estimated_hours": { "type": "number" },
        "weightage": { "type": ["number", "null"] },
        "prerequisite_topic_name": { "type": ["string", "null"] },
        "children": {
          "type": "array",
          "items": { "$ref": "#/definitions/enriched_topic" }
        }
      },
      "required": ["id", "difficulty", "estimated_hours", "weightage", "prerequisite_topic_name", "children"]
    }
  }
}
```

**Backend responsibility:** resolve `prerequisite_topic_name` → `prerequisite_topic_id` by matching within the same exam (fuzzy match on name, or re-ask AI with IDs if ambiguous). Reject self-references.

---

## 3. Planner (Module Master Plan)

**Purpose:** Given a topic the user is starting, its resources, and remaining exam context, generate a day-by-day master plan.

**Maps to:** `module_plans`, `module_plan_days`

### System Prompt

```
You are an exam preparation mentor creating a study plan for a single topic
("module") within a student's larger exam preparation. You think like an
experienced teacher: you sequence subtopics logically, respect prerequisites,
and never overload a single day.

You will receive:
- The topic and its subtopics (with difficulty and estimated hours)
- The student's own resource list for this module (videos, books, PYQs) and
  how they described what they intend to do
- Hours the student can study per day for this module
- Total days remaining until the exam
- Overall syllabus completion percentage so far

Your job: produce a day-by-day plan that fully covers the module's subtopics
within a reasonable number of days, respecting the student's daily hour
budget. Sequence subtopics so prerequisites come first. Distribute resource
usage (videos, book chapters, question sets) across days rather than
front-loading them. Include a short revision/consolidation day at the end
if the module spans more than 5 days.

Constraints:
- The total planned days must be realistic given estimated_hours vs
  daily_hours_available - do not compress a 20-hour topic into 2 days at
  3 hours/day.
- If total days requested by context (days_remaining_for_exam) is tight,
  prioritize high-weightage subtopics and note lower-priority ones as
  optional/first-to-cut in the day's notes, rather than silently dropping them.
- Do not exceed daily_hours_available by more than 10% on any single day.
```

### User Message Template

```
Exam: {{exam_name}}, exam date: {{exam_date}}, days remaining: {{days_remaining}}
Overall syllabus completion so far: {{overall_completion_pct}}%

Module topic: {{topic_name}}
Subtopics:
{{subtopics_json_with_difficulty_and_hours}}

Student's stated plan/resources (raw):
"""
{{raw_module_input_text}}
"""

Parsed resources:
{{module_resources_json}}

Daily hours available for this module: {{daily_hours_available}}
Expected total hours (student estimate, if given): {{expected_hours}}
```

### JSON Schema (response)

```json
{
  "type": "object",
  "properties": {
    "total_days": { "type": "integer" },
    "summary": { "type": "string" },
    "days": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "day_number": { "type": "integer" },
          "focus_subtopics": {
            "type": "array",
            "items": { "type": "string" }
          },
          "planned_hours": { "type": "number" },
          "tasks": {
            "type": "array",
            "items": {
              "type": "object",
              "properties": {
                "type": { "type": "string", "enum": ["video", "reading", "practice", "revision", "other"] },
                "description": { "type": "string" },
                "resource_ref": { "type": ["string", "null"] },
                "target_units": { "type": ["integer", "null"] }
              },
              "required": ["type", "description", "resource_ref", "target_units"]
            }
          },
          "notes": { "type": ["string", "null"] }
        },
        "required": ["day_number", "focus_subtopics", "planned_hours", "tasks", "notes"]
      }
    }
  },
  "required": ["total_days", "summary", "days"]
}
```

**Backend responsibility:** create one `module_plans` row (store full response in `ai_raw_response`), then one `module_plan_days` row per day entry.

---

## 4. Daily Planner

**Purpose:** Generate *today's* concrete task list, derived from the master plan day plus any carry-over from yesterday. This should be a light-weight call — it should not redesign the whole module.

**Maps to:** `daily_plans`

### System Prompt

```
You are generating a single day's study checklist for a student, based on
an already-approved master plan. You are not replanning the whole module -
you are producing execution-level tasks for today only, adjusted for
whatever was left incomplete yesterday.

You will receive:
- Today's planned focus from the master plan (subtopics, planned hours,
  originally planned tasks)
- Yesterday's completed and pending tasks, if any
- Any pending tasks that were pushed forward from previous days

Your job: produce today's task list. If there is carry-over from yesterday,
merge it sensibly with today's planned tasks WITHOUT exceeding roughly
110% of the student's daily hour budget. If merging would overload today,
prioritize: (1) carry-over tasks tied to prerequisite subtopics, (2)
highest-weightage subtopics, and explicitly push the rest one more day
forward, noting this in "deferred_notes".

Keep task descriptions concrete and specific (reference actual resource
names/units from context, not generic instructions).
```

### User Message Template

```
Module: {{topic_name}}, Day {{day_number}} of {{total_days}}
Master plan for today: {{module_plan_day_json}}
Daily hours available: {{daily_hours_available}}

Yesterday's completed tasks: {{yesterday_completed_json}}
Yesterday's pending/incomplete tasks: {{yesterday_pending_json}}
```

### JSON Schema (response)

```json
{
  "type": "object",
  "properties": {
    "plan_date": { "type": "string", "format": "date" },
    "planned_hours": { "type": "number" },
    "tasks": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "type": { "type": "string", "enum": ["video", "reading", "practice", "revision", "other"] },
          "description": { "type": "string" },
          "topic_ref": { "type": "string" },
          "target_units": { "type": ["integer", "null"] },
          "carried_over": { "type": "boolean" }
        },
        "required": ["type", "description", "topic_ref", "target_units", "carried_over"]
      }
    },
    "deferred_notes": { "type": ["string", "null"] }
  },
  "required": ["plan_date", "planned_hours", "tasks", "deferred_notes"]
}
```

---

## 5. Progress Analyzer

**Purpose:** Parse the student's free-text end-of-day report into structured completion data.

**Maps to:** `daily_reports`, `study_logs`

### System Prompt

```
You are extracting structured study progress from a student's free-text
end-of-day update. You will receive today's planned tasks and the student's
raw text describing what they actually did.

Match what the student describes back to the planned tasks as closely as
possible. A task is "completed" only if the student's text clearly indicates
it was finished. Partial progress (e.g. "watched half the video") should be
reflected in target_units_completed being less than target_units, with
status "partial". Anything not mentioned at all stays "not_mentioned" -
do not assume it was skipped or completed.

Also extract, if present in the text:
- actual_hours_spent (a number, or null if not stated)
- confidence_rating (1-5, only if the student explicitly rates themselves,
  otherwise null)
- delay_reason (short phrase, only if the student explains why something
  wasn't finished)
- mood_note (short phrase, only if relevant - e.g. tiredness, illness,
  distraction - otherwise null)

Never fabricate information not present in the text.
```

### User Message Template

```
Today's planned tasks:
{{today_planned_tasks_json}}

Student's end-of-day report (raw):
"""
{{raw_report_text}}
"""
```

### JSON Schema (response)

```json
{
  "type": "object",
  "properties": {
    "task_results": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "task_ref": { "type": "string" },
          "status": { "type": "string", "enum": ["completed", "partial", "not_mentioned"] },
          "units_completed": { "type": ["integer", "null"] }
        },
        "required": ["task_ref", "status", "units_completed"]
      }
    },
    "extra_progress_mentioned": {
      "type": "array",
      "items": { "type": "string" },
      "description": "Things the student did that weren't in the plan"
    },
    "actual_hours_spent": { "type": ["number", "null"] },
    "confidence_rating": { "type": ["integer", "null"] },
    "delay_reason": { "type": ["string", "null"] },
    "mood_note": { "type": ["string", "null"] }
  },
  "required": ["task_results", "extra_progress_mentioned", "actual_hours_spent", "confidence_rating", "delay_reason", "mood_note"]
}
```

**Backend responsibility:** write one `study_logs` row per topic touched, update `topics.status`/`completion_pct` via the rollup job, mark `daily_plans.status`.

---

## 6. Feedback Generator

**Purpose:** Produce the mentor-style message shown to the student, plus decide whether/how to adjust the remaining schedule.

**Maps to:** `feedback`, and (when adjustment needed) updates to future `module_plan_days`

### System Prompt

```
You are an experienced, encouraging exam mentor - like a teacher who has
tracked this student closely for months. You are giving feedback after a
single day's study check-in. You have full context on their pace, remaining
syllabus, and exam timeline.

Tone rules:
- Be specific. Reference actual numbers (tasks completed, hours studied,
  days remaining) - never generic praise like "Good job!" with nothing
  backing it.
- If the student did MORE than planned: acknowledge it concretely, and if
  it meaningfully shortens the module, say so and note where the saved
  time will go (e.g. added to revision buffer).
- If the student did LESS than planned: do not guilt-trip. Reassure them
  first using real numbers (e.g. days remaining, buffer still available),
  then clearly state the concrete adjustment being made to tomorrow's plan.
  Never suggest the exam goal is at risk unless the data genuinely shows
  high risk - and even then, frame it as a solvable pace problem, not a
  failure.
- Keep it short: 3-5 sentences of narrative feedback, plus the structured
  fields below. Avoid clichés and avoid over-using exclamation marks.

Decide pace_status and risk_level from the data, not from tone:
- pace_status "ahead" if completion is meaningfully outpacing the plan,
  "behind" if meaningfully behind, else "on_track".
- risk_level should reflect actual likelihood of missing the exam-date
  window, based on current pace vs. days remaining vs. syllabus remaining -
  not based on a single day's performance alone.

If an adjustment to the remaining plan is warranted (compressing or
redistributing future days), describe it in adjustments_made using topic
names and day numbers, but do NOT invent new numeric plans here - a
separate process handles the actual day-by-day recalculation. Only flag
whether adjustment is needed and a short description of what kind.
```

### User Message Template

```
Student full context:
- Exam: {{exam_name}}, {{days_remaining}} days remaining
- Overall syllabus completion: {{overall_completion_pct}}%
- Current module: {{topic_name}}, day {{day_number}} of {{total_days}}
- Historical average completion rate (last 7 days): {{avg_completion_pct_7d}}%
- Current streak: {{current_streak_days}} days

Today's plan vs actual:
{{task_results_json}}
Planned hours: {{planned_hours}}, actual hours: {{actual_hours_spent}}
Confidence rating (if given): {{confidence_rating}}
Delay reason (if given): {{delay_reason}}
Mood note (if given): {{mood_note}}
```

### JSON Schema (response)

```json
{
  "type": "object",
  "properties": {
    "performance_summary": { "type": "string" },
    "pace_status": { "type": "string", "enum": ["ahead", "on_track", "behind"] },
    "risk_level": { "type": "string", "enum": ["low", "medium", "high"] },
    "adjustment_needed": { "type": "boolean" },
    "adjustments_made": { "type": ["string", "null"] },
    "suggestions": { "type": "string" },
    "motivational_note": { "type": "string" },
    "next_focus": { "type": ["string", "null"] }
  },
  "required": ["performance_summary", "pace_status", "risk_level", "adjustment_needed", "adjustments_made", "suggestions", "motivational_note", "next_focus"]
}
```

**Backend responsibility:** if `adjustment_needed = true`, trigger the replanning routine (deterministic backend logic, not a fresh unconstrained AI call — see the redistribution algorithm we can design next) to actually rewrite future `module_plan_days`.

---

## 7. Analytics Agent

**Purpose:** Weekly/monthly review narrative + predictions. Runs on a schedule (cron), not per-interaction.

**Maps to:** `weekly_reviews`, `monthly_reviews`

### System Prompt

```
You are generating a periodic progress review for an exam-prep student,
in the voice of a mentor summarizing a week or month of work. You will
receive aggregated statistics already computed by the backend - do not
recompute numbers yourself, only interpret them.

Identify:
- Strong and weak topics/subjects based on completion rate and time spent
  vs estimated hours
- Whether current pace, if continued, would finish the syllabus before the
  exam date (use the provided projection numbers, don't calculate your own)
- One or two concrete, specific recommendations for the upcoming period
  (e.g. "prioritize Digital Logic this week" rather than "study harder")

Keep the narrative summary concise (4-6 sentences). Be honest about gaps
without being discouraging - always pair a concern with a specific,
achievable fix.
```

### User Message Template

```
Period: {{period_type}} ({{period_start}} to {{period_end}})
Exam: {{exam_name}}, {{days_remaining}} days remaining

Aggregated stats (precomputed):
{{aggregated_stats_json}}

Topic-level completion vs estimated hours:
{{topic_stats_json}}

Projection (precomputed): at current pace, projected completion date is
{{projected_completion_date}}; exam date is {{exam_date}}.
```

### JSON Schema (response)

```json
{
  "type": "object",
  "properties": {
    "narrative_summary": { "type": "string" },
    "strong_topics": { "type": "array", "items": { "type": "string" } },
    "weak_topics": { "type": "array", "items": { "type": "string" } },
    "on_track": { "type": "boolean" },
    "recommendations": {
      "type": "array",
      "items": { "type": "string" },
      "maxItems": 3
    }
  },
  "required": ["narrative_summary", "strong_topics", "weak_topics", "on_track", "recommendations"]
}
```

**Backend responsibility:** all numeric fields (`planned_hours`, `actual_hours`, `coverage_pct`, `projected_completion_date`, `required_daily_hours`, etc.) in `weekly_reviews`/`monthly_reviews` are computed by backend SQL aggregation, *not* by the AI — the AI only produces the narrative and qualitative fields (`ai_summary`, strong/weak topics, recommendations). This keeps your predictions trustworthy even if the LLM has an off day.

---

## Implementation Notes

**1. Validate, don't trust.**
After every AI call, run the JSON through a schema validator (e.g. `pydantic` models in FastAPI, or `zod` if any part of this is in Node) before touching the database. On validation failure: retry once with an error message appended to the prompt ("Your previous response failed validation: {error}. Return corrected JSON only."), then fall back to a safe default or flag for manual review — never let a malformed response corrupt state.

**2. Keep numeric/derived logic out of the AI where possible.**
Notice the pattern across agents 3–7: the AI is asked to *reason and sequence*, but wherever a number can be reliably computed by SQL (completion %, hours totals, projected dates), the backend computes it and only sends it *into* the prompt as context — never asks the AI to compute and return it as truth. This is what agent 7 makes explicit, but it applies everywhere. It keeps your dashboards accurate even when the LLM is being creative elsewhere.

**3. Chunk large context.**
The Difficulty Estimator and Planner especially can hit context limits on large syllabi. Batch by top-level topic rather than sending an entire exam's tree in one call — smaller batches also produce more reliable per-topic estimates.

**4. Model choice per agent.**
Agents 1–2 (parsing, estimation) and 7 (analytics) are less latency-sensitive and benefit from a stronger model since they run infrequently. Agents 3–6 (planner, daily planner, progress analyzer, feedback) run constantly and should prioritize speed/cost — a smaller/faster model is usually fine here since the task is narrow and well-scoped by the schema.

**5. Log everything.**
Every call here should write a row to `ai_interactions` with the exact `input_payload` and `output_payload` — this is what lets you debug "why did the plan look weird on day 4" without guessing.

# Module 4 — Analytics & AI Coach
## Detailed Implementation Plan

Goal for this module: turn the raw data accumulated by Modules 1-3 into weekly/monthly reviews, a revision engine (spaced repetition), confidence tracking, completion predictions, and full dashboards with graphs. This module reads far more than it writes — almost everything here is aggregation and interpretation of data that already exists, plus one new proactive scheduling system (revision).

By this point the architecture pattern should feel familiar — this doc leans on it rather than re-explaining it, and spends more time on the **SQL aggregation logic** and the **spaced repetition algorithm**, which are the genuinely new pieces.

---

## 1. New Dependencies

Backend — no new core libraries beyond what you already have (`apscheduler` continues to be used, now for weekly/monthly/revision jobs too).

Frontend — this is where something new is actually needed:

```
recharts          # already listed as available in your artifact/component environment,
                   # use it for the dashboard: line charts (hours over time), bar charts
                   # (topic-wise completion), heatmaps (custom SVG or a small heatmap lib)
date-fns           # date math for calendar/streak views
```

If you want a GitHub-style contribution heatmap for the study calendar, `recharts` doesn't have one built in — either build a simple custom SVG grid (straightforward: a grid of `<rect>` cells colored by intensity) or use a small dedicated library like `react-calendar-heatmap`. A custom SVG grid is usually less dependency overhead for something this simple.

---

## 2. New Database Tables in Play

Already defined in the schema doc:

- `weekly_reviews`
- `monthly_reviews`
- `revision_schedule`
- `confidence_logs`

This module reads heavily from `study_logs`, `daily_reports`, `topics`, `module_plan_days`, `feedback` — all owned by earlier modules. No writes back into those tables from this module (analytics should never mutate the data it's summarizing).

---

## 3. Project Structure Additions

```
backend/
  app/
    models/
      weekly_review.py
      monthly_review.py
      revision_schedule.py
      confidence_log.py
    schemas/
      weekly_review.py
      monthly_review.py
      revision.py
      dashboard.py                    # composite response schemas for chart endpoints
      ai_analytics.py                 # agent 7 schema
    api/
      routes/
        analytics.py                  # weekly/monthly review retrieval, dashboard data
        revision.py                   # revision queue, mark-done
        confidence.py                 # log confidence ratings
    services/
      analytics_service.py            # SQL aggregation, orchestrates agent 7
      revision_service.py             # spaced repetition scheduling logic
      prediction_service.py           # completion-date projection math
      scheduler_jobs.py               # weekly/monthly/revision cron jobs (extends Module 3's scheduler.py)
      ai/
        analytics_agent.py            # agent 7
        prompts/
          analytics_agent.txt
    tests/
      test_aggregation_queries.py
      test_revision_scheduling.py
      test_prediction_service.py

frontend/
  src/
    pages/
      DashboardPage.tsx               # the main overview — combines everything
      WeeklyReviewPage.tsx
      MonthlyReviewPage.tsx
      RevisionQueuePage.tsx
      TopicHeatmapPage.tsx
    components/
      charts/
        HoursOverTimeChart.tsx        # recharts LineChart
        TopicCompletionBarChart.tsx   # recharts BarChart
        StudyCalendarHeatmap.tsx      # custom SVG grid
        ConsistencyGauge.tsx
      RevisionCard.tsx
      ConfidenceSlider.tsx
```

---

## 4. Architecture Overview — Three Independent Subsystems

Module 4 isn't one pipeline like Module 2 or 3 — it's three loosely-coupled subsystems that all read from the same underlying data:

```
┌─────────────────────┐   ┌─────────────────────┐   ┌─────────────────────┐
│  A. Periodic Reviews │   │  B. Revision Engine  │   │  C. Prediction &     │
│  (weekly/monthly)    │   │  (spaced repetition)  │   │  Dashboard Queries   │
│                       │   │                       │   │                       │
│  Scheduled job        │   │  Triggered on topic   │   │  On-demand, computed  │
│  -> SQL aggregation    │   │  completion + on a    │   │  live from DB on      │
│  -> Agent 7 narrative  │   │  daily cron check      │   │  every dashboard load │
│  -> store review       │   │  -> revision_schedule │   │  -> no AI involved     │
└─────────────────────┘   └─────────────────────┘   └─────────────────────┘
```

Building them as separate subsystems (separate services, separate jobs) rather than one "analytics pipeline" matters because they run on different triggers and have completely different failure tolerances — a failed weekly review generation shouldn't block revision scheduling, and dashboard queries need to be fast and synchronous (a user is staring at a loading spinner), while the other two run in the background.

---

## 5. Subsystem A — Weekly & Monthly Reviews

### 5.1 The core principle (repeated from the prompt doc, worth repeating here in code form)

**All numeric fields are computed by SQL. The AI only writes the narrative and picks strong/weak topics from data you hand it.** This is the most important rule in this whole module — do not let this slip because it's tempting to just "ask the AI for a summary" of raw logs.

### 5.2 Weekly review generation

```python
# services/analytics_service.py

async def generate_weekly_review(db, exam_id: UUID, week_start: date) -> WeeklyReview:
    week_end = week_start + timedelta(days=6)
    stats = await _compute_weekly_stats(db, exam_id, week_start, week_end)

    ai_response = await analytics_agent.generate_review(
        exam_name=..., period_type="weekly", period_start=week_start, period_end=week_end,
        days_remaining=stats.days_remaining, aggregated_stats=stats.to_dict(),
        topic_stats=stats.topic_breakdown, projected_completion_date=stats.projected_completion,
        exam_date=stats.exam_date,
    )

    review = WeeklyReview(
        exam_id=exam_id, week_start_date=week_start, week_end_date=week_end,
        planned_hours=stats.planned_hours, actual_hours=stats.actual_hours,
        topics_completed=stats.topics_completed, skipped_days=stats.skipped_days,
        avg_productivity_pct=stats.avg_productivity_pct,
        strong_topics=ai_response.strong_topics, weak_topics=ai_response.weak_topics,
        ai_summary=ai_response.narrative_summary, ai_raw_response=ai_response.model_dump(),
    )
    db.add(review)
    await db.commit()
    return review
```

### 5.3 The aggregation query — this is the real work

```python
async def _compute_weekly_stats(db, exam_id: UUID, week_start: date, week_end: date) -> WeeklyStats:
    # Planned vs actual hours
    planned_hours = await db.scalar(
        select(func.sum(ModulePlanDay.planned_hours))
        .join(ModuleStart, ModuleStart.id == ModulePlanDay.module_plan_id)  # via module_plans
        .where(
            ModuleStart.exam_id == exam_id,
            ModulePlanDay.planned_date.between(week_start, week_end),
        )
    ) or 0

    actual_hours = await db.scalar(
        select(func.sum(DailyReport.actual_hours))
        .join(DailyPlan, DailyPlan.id == DailyReport.daily_plan_id)
        .join(ModuleStart, ModuleStart.id == DailyPlan.module_start_id)
        .where(
            ModuleStart.exam_id == exam_id,
            DailyPlan.plan_date.between(week_start, week_end),
        )
    ) or 0

    topics_completed = await db.scalar(
        select(func.count(Topic.id))
        .where(
            Topic.exam_id == exam_id,
            Topic.is_leaf == True,
            Topic.status == "completed",
            Topic.updated_at.between(week_start, week_end + timedelta(days=1)),
        )
    )

    # Days with zero study_logs in this window = skipped days
    active_days = await db.scalars(
        select(func.distinct(DailyPlan.plan_date))
        .join(ModuleStart).where(ModuleStart.exam_id == exam_id)
        .where(DailyPlan.plan_date.between(week_start, week_end))
        .where(DailyPlan.status.in_(["completed", "partially_completed"]))
    )
    skipped_days = 7 - len(set(active_days.all()))

    avg_productivity_pct = (actual_hours / planned_hours * 100) if planned_hours else None

    topic_breakdown = await _get_topic_time_breakdown(db, exam_id, week_start, week_end)

    projection = await prediction_service.project_completion(db, exam_id)

    return WeeklyStats(
        planned_hours=planned_hours, actual_hours=actual_hours,
        topics_completed=topics_completed, skipped_days=skipped_days,
        avg_productivity_pct=avg_productivity_pct, topic_breakdown=topic_breakdown,
        days_remaining=projection.days_remaining, exam_date=projection.exam_date,
        projected_completion=projection.projected_date,
    )
```

**Implementation note:** write these as a handful of separate, readable queries (as above) rather than one giant joined mega-query. Aggregation bugs are painful to debug in a 200-line SQL statement and easy to unit-test individually when split up. Performance is a non-issue at this data scale (thousands of rows per user, not millions).

### 5.4 Monthly review

Same shape, coarser grain (`month` instead of `week_start/week_end`), plus the two prediction fields (`projected_completion_date`, `required_daily_hours`) — computed by `prediction_service` (section 7), never by the AI.

### 5.5 Scheduling

```python
# services/scheduler_jobs.py (extends Module 3's scheduler.py)
scheduler.add_job(generate_all_weekly_reviews, "cron", day_of_week="sun", hour=23, minute=0)
scheduler.add_job(generate_all_monthly_reviews, "cron", day=1, hour=1, minute=0)  # 1st of month
```

Same fault-isolation pattern as Module 3's daily job — wrap each exam's generation in its own try/except inside the batch loop, bounded concurrency via semaphore.

**Also expose on-demand generation:** `POST /exams/{id}/weekly-review?week_start=...` — useful for backfilling, testing, and letting a curious user trigger "how am I doing this week" mid-week rather than waiting for Sunday.

---

## 6. Subsystem B — Revision Engine (Spaced Repetition)

### 6.1 The scheduling algorithm

Classic spaced repetition intervals, as you specified: 1 day, 3 days, 7 days, 15 days, 30 days after completion. Keep this as a simple configurable list rather than implementing a full SM-2/Anki-style adaptive algorithm — that's real added complexity for marginal benefit at this stage, and a fixed schedule is easy to reason about and explain to the user.

```python
# services/revision_service.py

REVISION_INTERVALS_DAYS = [1, 3, 7, 15, 30]

async def schedule_revisions_for_topic(db, topic: Topic):
    """Called when a leaf topic transitions to status='completed'."""
    completion_date = date.today()
    for i, interval in enumerate(REVISION_INTERVALS_DAYS, start=1):
        db.add(RevisionSchedule(
            topic_id=topic.id,
            exam_id=topic.exam_id,
            revision_number=i,
            scheduled_date=completion_date + timedelta(days=interval),
            status="pending",
            trigger_reason="spaced_repetition",
        ))
    await db.commit()
```

**Where this gets triggered:** hook into the same `recalculate_completion` function from Module 1 (or the point right after it's called in Module 3's `process_checkin`) — when a leaf topic's status flips to `completed`, call `schedule_revisions_for_topic`. This is the one place Module 4 does write into a shared flow, but it's an *additive* hook, not a modification of Module 1/3's core logic — keep it as a clearly separate function call, not inlined into `recalculate_completion` itself, so Module 1's function stays focused on its one job.

### 6.2 Low-confidence triggers an extra revision

```python
async def maybe_schedule_confidence_revision(db, topic_id: UUID, rating: int):
    db.add(ConfidenceLog(topic_id=topic_id, rating=rating, context="module_complete"))
    if rating <= 2:
        # insert an earlier, additional revision — don't wait for the day-1 spaced one
        db.add(RevisionSchedule(
            topic_id=topic_id, exam_id=..., revision_number=0,  # 0 = out-of-band, before revision_number=1
            scheduled_date=date.today() + timedelta(days=1),
            status="pending", trigger_reason="low_confidence",
        ))
    await db.commit()
```

Call this from a new endpoint the frontend hits right after a module is marked complete: `POST /topics/{id}/confidence` with `{ rating: 1-5 }`.

### 6.3 Revision queue and completion

```python
# api/routes/revision.py
@router.get("/exams/{id}/revision-queue")
async def get_revision_queue(exam_id: UUID, db=Depends(get_db)):
    today_and_overdue = await db.scalars(
        select(RevisionSchedule)
        .where(
            RevisionSchedule.exam_id == exam_id,
            RevisionSchedule.status == "pending",
            RevisionSchedule.scheduled_date <= date.today(),
        )
        .order_by(RevisionSchedule.scheduled_date)
    )
    return today_and_overdue.all()

@router.post("/revisions/{id}/complete")
async def complete_revision(id: UUID, db=Depends(get_db)):
    revision = await db.get(RevisionSchedule, id)
    revision.status = "done"
    revision.completed_at = datetime.utcnow()
    await db.commit()
    # optionally log a fresh confidence rating here too, to track improvement over revisions
```

**Where does the revision queue show up for the user?** Feed it into Module 3's daily task generation as an optional extra context: when building today's daily plan (Pipeline A in Module 3), also check `get_revision_queue` and, if items are due, either (a) surface them as a separate "Today's Revisions" section on `TodayPage` independent of the module's daily tasks, or (b) pass them into the Daily Planner agent's context so it can weave a revision task into the day. Option (a) is simpler and more predictable — recommended, since it keeps Module 3's daily planner logic unchanged and revision surfaces as its own UI section.

---

## 7. Subsystem C — Predictions & Dashboard Queries

All synchronous, on-demand, no AI, computed live from the database on each request — this is what makes the dashboard feel fast and always-current.

### 7.1 Completion projection

```python
# services/prediction_service.py

async def project_completion(db, exam_id: UUID) -> ProjectionResult:
    exam = await exam_service.get(db, exam_id)

    total_estimated_hours = await db.scalar(
        select(func.sum(Topic.estimated_hours)).where(Topic.exam_id == exam_id, Topic.is_leaf == True)
    ) or 0
    completed_hours = await db.scalar(
        select(func.sum(Topic.estimated_hours))
        .where(Topic.exam_id == exam_id, Topic.is_leaf == True, Topic.status == "completed")
    ) or 0
    remaining_hours = total_estimated_hours - completed_hours

    # average actual daily pace over the last N days (rolling window smooths out single bad/good days)
    avg_daily_hours = await _compute_rolling_avg_daily_hours(db, exam_id, window_days=14)

    if avg_daily_hours and avg_daily_hours > 0:
        days_needed = math.ceil(remaining_hours / avg_daily_hours)
        projected_date = date.today() + timedelta(days=days_needed)
    else:
        projected_date = None  # not enough data yet, e.g. first week

    days_remaining_exam = (exam.exam_date - date.today()).days if exam.exam_date else None
    required_daily_hours = (
        remaining_hours / days_remaining_exam if days_remaining_exam and days_remaining_exam > 0 else None
    )

    return ProjectionResult(
        exam_date=exam.exam_date, days_remaining=days_remaining_exam,
        projected_date=projected_date, required_daily_hours=required_daily_hours,
        on_track=(projected_date <= exam.exam_date) if (projected_date and exam.exam_date) else None,
    )
```

**Why a rolling 14-day average instead of all-time average:** all-time average gets diluted by a slow first week and reacts too slowly to real, recent changes in pace. A rolling window keeps the projection responsive to how the student is *actually* doing lately, which is what "should I be worried right now" needs to reflect.

### 7.2 Dashboard composite endpoint

Build one endpoint that returns everything `DashboardPage` needs in a single round trip, rather than the frontend firing five separate requests on load:

```python
# api/routes/analytics.py
@router.get("/exams/{id}/dashboard")
async def get_dashboard(exam_id: UUID, db=Depends(get_db)):
    return DashboardResponse(
        overall_progress=await analytics_service.get_overall_progress(db, exam_id),
        current_module=await module_service.get_active_module_summary(db, exam_id),
        timeline=await prediction_service.project_completion(db, exam_id),
        performance=await analytics_service.get_performance_stats(db, exam_id),  # streak, avg hours, consistency
        revision_queue_count=await revision_service.count_due(db, exam_id),
        recent_feedback=await feedback_service.get_recent(db, exam_id, limit=3),
    )
```

Run the independent sub-queries concurrently with `asyncio.gather` rather than sequentially — none of these depend on each other, and this is the single highest-traffic endpoint in the app (loaded every time a user opens the dashboard), so it's worth the small effort to parallelize.

### 7.3 Consistency score

```python
async def compute_consistency_score(db, exam_id: UUID, window_days: int = 30) -> float:
    """% of days in the window where the student logged any study activity."""
    window_start = date.today() - timedelta(days=window_days)
    active_days = await db.scalar(
        select(func.count(func.distinct(DailyPlan.plan_date)))
        .join(ModuleStart).where(ModuleStart.exam_id == exam_id)
        .where(DailyPlan.plan_date >= window_start)
        .where(DailyPlan.status.in_(["completed", "partially_completed"]))
    )
    return round((active_days / window_days) * 100, 1)
```

### 7.4 Streak calculation

```python
async def compute_current_streak(db, exam_id: UUID) -> int:
    """Consecutive days up to and including today/yesterday with logged activity."""
    active_dates = await db.scalars(
        select(func.distinct(DailyPlan.plan_date))
        .join(ModuleStart).where(ModuleStart.exam_id == exam_id)
        .where(DailyPlan.status.in_(["completed", "partially_completed"]))
        .order_by(DailyPlan.plan_date.desc())
    )
    dates = set(active_dates.all())
    streak = 0
    check_date = date.today()
    # allow today to be "not yet studied" without breaking streak, start check from yesterday if today's empty
    if check_date not in dates:
        check_date -= timedelta(days=1)
    while check_date in dates:
        streak += 1
        check_date -= timedelta(days=1)
    return streak
```

---

## 8. Frontend Dashboard Implementation

### 8.1 Chart components (recharts)

```tsx
// components/charts/HoursOverTimeChart.tsx
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer } from "recharts";

export function HoursOverTimeChart({ data }: { data: { date: string; planned: number; actual: number }[] }) {
  return (
    <ResponsiveContainer width="100%" height={240}>
      <LineChart data={data}>
        <XAxis dataKey="date" />
        <YAxis />
        <Tooltip />
        <Line type="monotone" dataKey="planned" stroke="#94a3b8" strokeDasharray="4 4" />
        <Line type="monotone" dataKey="actual" stroke="#4f46e5" strokeWidth={2} />
      </LineChart>
    </ResponsiveContainer>
  );
}
```

Feed this from a dedicated endpoint: `GET /exams/{id}/stats/hours-timeline?days=30` — a simple `GROUP BY plan_date` query, separate from the composite dashboard endpoint since it's chart-specific data the initial dashboard load doesn't need immediately (lazy-load when the chart section scrolls into view, or fetch alongside but keep it a distinct query for cache/invalidation clarity with React Query).

### 8.2 Topic heatmap (custom SVG grid)

Simple enough to hand-roll — a grid of topics colored by `completion_pct`:

```tsx
// components/charts/StudyCalendarHeatmap.tsx (calendar version — GitHub-style)
export function StudyCalendarHeatmap({ dailyHours }: { dailyHours: Record<string, number> }) {
  const weeks = buildWeekGrid(dailyHours); // date-fns helper, groups last ~16 weeks into a 2D array
  const intensity = (hours: number) => hours === 0 ? "#f1f5f9" : hours < 2 ? "#c7d2fe" : hours < 4 ? "#818cf8" : "#4338ca";
  return (
    <svg width={16 * 14} height={7 * 14}>
      {weeks.map((week, wi) => week.map((day, di) => (
        <rect key={`${wi}-${di}`} x={wi * 14} y={di * 14} width={12} height={12} rx={2}
          fill={intensity(dailyHours[day.dateStr] || 0)} />
      )))}
    </svg>
  );
}
```

### 8.3 React Query setup for the dashboard

```tsx
// pages/DashboardPage.tsx
const { data: dashboard, isLoading } = useQuery({
  queryKey: ["dashboard", examId],
  queryFn: () => api.getDashboard(examId),
  staleTime: 60_000, // dashboard data doesn't need to refetch on every re-render, 1 min is plenty fresh
});
```

Use `staleTime` deliberately here — this is a read-heavy module and there's no reason to hammer the aggregation endpoint on every component mount.

---

## 9. Testing Strategy

- **`test_aggregation_queries.py`** — seed a test DB with known fixture data (specific `daily_plans`, `daily_reports`, `topics` with known states) and assert the aggregation functions return exactly the expected numbers. This is pure arithmetic correctness — treat it with the same rigor as the replanning algorithm tests in Module 3.
- **`test_revision_scheduling.py`** — assert `schedule_revisions_for_topic` creates exactly 5 rows at the correct offsets; assert `maybe_schedule_confidence_revision` only fires the extra revision when `rating <= 2`.
- **`test_prediction_service.py`** — table-driven tests: given fixed `remaining_hours` and `avg_daily_hours`, assert exact `projected_date` and `required_daily_hours`. Include the zero-data edge case (brand new exam, no study logs yet — should return `None`, not divide-by-zero crash).
- **Mock the AI layer** for weekly/monthly review generation tests, same as every prior module — the aggregation logic and the AI narrative are separately testable concerns.

---

## 10. Suggested Build Order Within Module 4

1. New models + migration for `weekly_reviews`, `monthly_reviews`, `revision_schedule`, `confidence_logs`.
2. **Prediction service first** (section 7.1) — it's pure math, no AI, and both the dashboard and monthly reviews depend on it. Test it thoroughly in isolation.
3. Dashboard composite endpoint + basic stats functions (consistency, streak) — get `DashboardPage` showing real numbers before adding charts.
4. Revision engine (section 6) — hook `schedule_revisions_for_topic` into the existing completion flow, build the queue endpoint, wire into `TodayPage` as a separate section.
5. Confidence logging endpoint + the low-confidence-triggers-revision logic.
6. Weekly review aggregation query + Agent 7 integration + scheduled job.
7. Monthly review (same pattern, coarser grain) + the two prediction fields.
8. Frontend charts: hours-over-time, topic completion bar chart, calendar heatmap.
9. `RevisionQueuePage`, `WeeklyReviewPage`, `MonthlyReviewPage`.
10. Tests: aggregation correctness, revision scheduling, prediction edge cases.
11. Final polish pass across the whole app: loading states, empty states (new exam with no data yet — every chart/stat should degrade gracefully, not crash or show garbage), error boundaries.

---

## 11. What NOT to Over-Build

- **Don't implement full SM-2/Anki-style adaptive spaced repetition.** Fixed intervals (1/3/7/15/30 days) deliver most of the value with a fraction of the complexity and are far easier to explain to a user ("your next revision is in 3 days") than an opaque adaptive algorithm.
- **Don't let the AI compute any number that appears in a dashboard.** Every chart, every stat card, every projection — SQL/Python only. The AI's entire footprint in this module is narrative text and topic-name lists (strong/weak topics, recommendations).
- **Don't build real-time dashboards (websockets/polling for live updates).** Study data updates once or twice a day (morning plan, evening check-in) — a dashboard that refetches on navigation/mount is more than sufficient; live-updating infrastructure would be solving a problem this app doesn't have.
- **Don't build cross-exam analytics yet** (e.g. "compare your GATE prep pace to your GRE prep pace") unless a user explicitly asks for it later — scope this module to one exam's full picture, which is already a lot of surface area.

---

## Module 4 Completion = Full Application Complete

At the end of this module, the full loop your original design described is implemented end-to-end: one-time exam + syllabus setup, AI-structured topic tree, per-module planning, daily adaptive execution with mentor feedback, and weekly/monthly reflection with predictions and spaced revision — all built on the same consistent architectural principle across all four modules: **the AI reasons and writes narrative; the database and deterministic backend code own every number and every constraint.**
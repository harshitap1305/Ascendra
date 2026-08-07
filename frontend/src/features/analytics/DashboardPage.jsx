import { useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { analyticsService } from '../../services'
import AppLayout from '../../layouts/AppLayout'
import ReadinessGauge from '../../components/ReadinessGauge'
import StatCard from '../../components/StatCard'
import HoursTimelineChart from '../../components/charts/HoursTimelineChart'
import TopicCompletionBarChart from '../../components/charts/TopicCompletionBarChart'
import StudyCalendarHeatmap from '../../components/charts/StudyCalendarHeatmap'
import FeedbackCard from '../../components/FeedbackCard'

function ProgressRing({ pct }) {
  const r = 30, stroke = 5
  const circ = 2 * Math.PI * r
  const filled = (pct / 100) * circ
  return (
    <svg width={74} height={74} viewBox="0 0 74 74" className="rotate-[-90deg]">
      <circle cx={37} cy={37} r={r} fill="none" stroke="#1e293b" strokeWidth={stroke} />
      <circle
        cx={37} cy={37} r={r} fill="none"
        stroke={pct === 100 ? '#10b981' : '#6366f1'} strokeWidth={stroke}
        strokeLinecap="round"
        strokeDasharray={`${filled} ${circ - filled}`}
        style={{ transition: 'stroke-dasharray 0.8s ease-out' }}
      />
    </svg>
  )
}

export default function DashboardPage() {
  const { examId } = useParams()
  const [timelineDays, setTimelineDays] = useState(30)

  const { data: dashboard, isLoading } = useQuery({
    queryKey: ['dashboard', examId],
    queryFn: () => analyticsService.getDashboard(examId),
    staleTime: 60_000,
  })

  const { data: timeline = [] } = useQuery({
    queryKey: ['hours-timeline', examId, timelineDays],
    queryFn: () => analyticsService.getHoursTimeline(examId, timelineDays),
    staleTime: 60_000,
  })

  const { data: topicCompletion = [] } = useQuery({
    queryKey: ['topic-completion', examId],
    queryFn: () => analyticsService.getTopicCompletion(examId),
    staleTime: 120_000,
  })

  const { data: revisionQueue = [] } = useQuery({
    queryKey: ['revision-queue', examId],
    queryFn: () => analyticsService.getRevisionQueue(examId),
    staleTime: 30_000,
  })

  if (isLoading) {
    return (
      <AppLayout>
        <div className="flex items-center justify-center py-32">
          <div className="w-10 h-10 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin" />
        </div>
      </AppLayout>
    )
  }

  const dp = dashboard
  const overall = dp?.overall_progress
  const perf = dp?.performance
  const tl = dp?.timeline

  // Build heatmap data from timeline
  const heatmapData = timeline.reduce((acc, d) => {
    acc[d.date] = d.actual
    return acc
  }, {})

  const paceColor = tl?.on_track === true ? 'text-emerald-400' : tl?.on_track === false ? 'text-red-400' : 'text-secondary/70'

  return (
    <AppLayout>
      <div className="max-w-5xl mx-auto space-y-6 pb-12">
        {/* Header */}
        <div className="flex items-start justify-between flex-wrap gap-4">
          <div>
            <h1 className="text-2xl font-bold text-secondary">{overall?.exam_name ?? 'Dashboard'}</h1>
            <div className="flex items-center gap-3 mt-1 flex-wrap">
              {tl?.days_remaining != null && (
                <span className={`text-sm font-medium ${tl.days_remaining < 30 ? 'text-red-400' : 'text-secondary/70'}`}>
                  🗓 {tl.days_remaining} days until exam
                </span>
              )}
              {tl?.on_track != null && (
                <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${tl.on_track ? 'bg-emerald-500/20 text-emerald-400' : 'bg-red-500/20 text-red-400'}`}>
                  {tl.on_track ? '✓ On Track' : '⚠ Behind Pace'}
                </span>
              )}
            </div>
          </div>
          <div className="flex gap-2 flex-wrap">
            {dp?.revision_queue_count > 0 && (
              <Link
                to={`/exams/${examId}/revision-queue`}
                className="btn-secondary text-sm relative"
              >
                🔄 Revisions
                <span className="absolute -top-1.5 -right-1.5 bg-red-500 text-secondary text-xs w-4 h-4 rounded-full flex items-center justify-center font-bold">
                  {dp.revision_queue_count}
                </span>
              </Link>
            )}
            <Link to={`/exams/${examId}/weekly-reviews`} className="btn-secondary text-sm">
              📋 Weekly Review
            </Link>
          </div>
        </div>

        {/* Top row — Readiness gauge + overall progress + stat cards */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {/* Readiness gauge spans 2 columns */}
          <div className="sm:col-span-2">
            <ReadinessGauge
              score={dp?.readiness_score ?? 0}
              breakdown={dp?.readiness_breakdown ?? {}}
            />
          </div>

          {/* Stat cards */}
          <StatCard
            label="Overall Progress"
            value={`${overall?.completion_pct ?? 0}%`}
            icon="📚"
            subtext={`${overall?.completed_leaf_topics ?? 0} / ${overall?.total_leaf_topics ?? 0} topics`}
          />
          <StatCard
            label="Study Streak"
            value={`${perf?.current_streak_days ?? 0} days`}
            icon="🔥"
            subtext={`Best: ${perf?.longest_streak_days ?? 0} days`}
            trend={perf?.current_streak_days > 0 ? 'Active' : undefined}
            trendUp={true}
          />
          <StatCard
            label="Consistency"
            value={`${perf?.consistency_score ?? 0}%`}
            icon="📅"
            subtext="Last 30 days"
          />
          <StatCard
            label="Avg Daily Hours"
            value={perf?.avg_daily_hours_14d ? `${perf.avg_daily_hours_14d}h` : '—'}
            icon="⏱"
            subtext="14-day rolling avg"
          />
          <StatCard
            label="Total Hours"
            value={`${perf?.total_hours_studied ?? 0}h`}
            icon="📖"
            subtext="All time studied"
          />
          <StatCard
            label="Required Daily"
            value={tl?.required_daily_hours ? `${tl.required_daily_hours}h` : '—'}
            icon="🎯"
            subtext="To finish before exam"
            trend={tl?.on_track === false ? 'Behind pace' : undefined}
            trendUp={false}
          />
        </div>

        {/* Hours Timeline Chart */}
        <HoursTimelineChart
          data={timeline}
          onRangeChange={setTimelineDays}
        />

        {/* Progress Ring + Active Module */}
        {dp?.active_module && (
          <div className="card flex items-center gap-5">
            <div className="relative shrink-0">
              <ProgressRing pct={dp.active_module.module_completion_pct} />
              <div className="absolute inset-0 flex items-center justify-center text-xs font-bold text-secondary">
                {Math.round(dp.active_module.module_completion_pct)}%
              </div>
            </div>
            <div className="min-w-0">
              <p className="text-secondary/70 text-xs uppercase tracking-wide mb-0.5">Current Module</p>
              <h3 className="text-secondary font-semibold truncate">{dp.active_module.topic_name}</h3>
              <p className="text-secondary/70 text-sm">{dp.active_module.total_days}-day plan · {dp.active_module.status}</p>
            </div>
          </div>
        )}

        {/* Two-column: Topic Bar Chart + Calendar Heatmap */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <TopicCompletionBarChart data={topicCompletion} />
          <StudyCalendarHeatmap dailyHours={heatmapData} />
        </div>

        {/* Revision Queue preview */}
        {revisionQueue.length > 0 && (
          <div className="card">
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-sm font-semibold text-secondary">
                🔄 Revisions Due ({revisionQueue.length})
              </h3>
              <Link
                to={`/exams/${examId}/revision-queue`}
                className="text-indigo-400 hover:text-indigo-300 text-xs"
              >
                View all →
              </Link>
            </div>
            <div className="space-y-2">
              {revisionQueue.slice(0, 3).map(r => (
                <div key={r.id} className="flex items-center justify-between py-2 border-b border-secondary last:border-0">
                  <div>
                    <span className="text-secondary text-sm font-medium">{r.topic_name}</span>
                    <span className="text-secondary/70 text-xs ml-2">{r.revision_label}</span>
                  </div>
                  {r.days_overdue > 0 && (
                    <span className="badge-high text-xs">{r.days_overdue}d overdue</span>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Recent Feedback */}
        {dp?.recent_feedback?.length > 0 && (
          <div>
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-sm font-semibold text-secondary">Recent Check-in Feedback</h3>
              <Link
                to={`/exams/${examId}/feedback`}
                className="text-indigo-400 hover:text-indigo-300 text-xs"
              >
                All feedback →
              </Link>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              {dp.recent_feedback.map(fb => (
                <FeedbackCard key={fb.id} feedback={fb} compact />
              ))}
            </div>
          </div>
        )}

        {/* Projection info bar */}
        {tl?.projected_finish_date && (
          <div className={`rounded-xl border p-4 text-sm ${
            tl.on_track
              ? 'bg-emerald-500/10 border-emerald-500/30'
              : 'bg-amber-500/10 border-amber-500/30'
          }`}>
            <div className="flex items-center gap-2 flex-wrap">
              <span className="text-lg">{tl.on_track ? '✅' : '⏳'}</span>
              <span className="text-secondary">
                At your current pace ({perf?.avg_daily_hours_14d ?? '?'}h/day), you'll finish on{' '}
                <span className="font-semibold text-secondary">{tl.projected_finish_date}</span>
                {tl.on_track
                  ? ` — ${tl.days_remaining} days before exam.`
                  : ` — you need ${tl.required_daily_hours}h/day to finish on time.`}
              </span>
            </div>
          </div>
        )}
      </div>
    </AppLayout>
  )
}

import { useState } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { analyticsService } from '../../services'
import AppLayout from '../../layouts/AppLayout'

function ToneTag({ tone }) {
  const map = {
    encouraging: { label: '🌟 Encouraging', cls: 'badge-low' },
    urgent: { label: '⚠ Urgent', cls: 'badge-high' },
    balanced: { label: '⚖ Balanced', cls: 'badge-medium' },
  }
  const t = map[tone] || map.balanced
  return <span className={t.cls}>{t.label}</span>
}

export default function WeeklyReviewPage() {
  const { examId } = useParams()
  const queryClient = useQueryClient()
  const [generating, setGenerating] = useState(false)

  const { data: reviews = [], isLoading } = useQuery({
    queryKey: ['weekly-reviews', examId],
    queryFn: () => analyticsService.listWeeklyReviews(examId),
  })

  const generateMutation = useMutation({
    mutationFn: () => analyticsService.generateWeeklyReview(examId),
    onMutate: () => setGenerating(true),
    onSettled: () => setGenerating(false),
    onSuccess: () => queryClient.invalidateQueries(['weekly-reviews', examId]),
  })

  return (
    <AppLayout>
      <div className="max-w-3xl mx-auto">
        {/* Header */}
        <div className="flex items-start justify-between mb-6 flex-wrap gap-4">
          <div>
            <Link
              to={`/exams/${examId}/dashboard`}
              className="text-secondary/70 hover:text-secondary text-sm mb-1 transition-colors block"
            >
              ← Dashboard
            </Link>
            <h1 className="text-2xl font-bold text-secondary">Weekly Reviews</h1>
            <p className="text-secondary/70 text-sm mt-1">AI-powered summaries generated every Sunday</p>
          </div>
          <button
            id="generate-weekly-btn"
            onClick={() => generateMutation.mutate()}
            disabled={generating}
            className="btn-primary text-sm"
          >
            {generating ? '⏳ Generating…' : '✨ Generate Now'}
          </button>
        </div>

        {isLoading ? (
          <div className="flex justify-center py-16">
            <div className="w-8 h-8 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin" />
          </div>
        ) : reviews.length === 0 ? (
          <div className="card text-center py-12">
            <p className="text-4xl mb-3">📋</p>
            <h3 className="text-secondary font-semibold mb-2">No weekly reviews yet</h3>
            <p className="text-secondary/70 text-sm mb-4">Reviews are auto-generated every Sunday, or you can generate one now.</p>
            <button onClick={() => generateMutation.mutate()} disabled={generating} className="btn-primary text-sm mx-auto">
              {generating ? 'Generating…' : 'Generate this week\'s review'}
            </button>
          </div>
        ) : (
          <div className="space-y-6">
            {reviews.map(r => (
              <div key={r.id} className="card space-y-4">
                {/* Header */}
                <div className="flex items-start justify-between flex-wrap gap-2">
                  <div>
                    <h2 className="text-secondary font-bold text-lg">
                      Week of {r.week_start_date}
                    </h2>
                    <p className="text-secondary/70 text-xs mt-0.5">
                      {r.week_start_date} → {r.week_end_date}
                      {r.trigger_reason === 'missed_days_risk' && (
                        <span className="ml-2 badge-high text-xs">Risk Alert</span>
                      )}
                    </p>
                  </div>
                  <div className="flex gap-2 flex-wrap">
                    <ToneTag tone={r.ai_tone} />
                    <span className="text-slate-600 text-xs self-end">{r.exam_completion_pct?.toFixed(1)}% overall</span>
                  </div>
                </div>

                {/* Stats bar */}
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                  {[
                    { label: 'Planned', value: `${r.planned_hours}h` },
                    { label: 'Actual', value: `${r.actual_hours}h`, highlight: r.actual_hours >= r.planned_hours },
                    { label: 'Topics Done', value: r.topics_completed },
                    { label: 'Active Days', value: `${r.active_days}/7` },
                  ].map(s => (
                    <div key={s.label} className="bg-tan/60 rounded-lg px-3 py-2">
                      <p className="text-secondary/70 text-xs">{s.label}</p>
                      <p className={`font-bold text-lg ${s.highlight ? 'text-emerald-400' : 'text-secondary'}`}>{s.value}</p>
                    </div>
                  ))}
                </div>

                {/* Projected finish */}
                {r.projected_finish_date && (
                  <div className="text-xs text-secondary/70">
                    📅 Projected finish: <span className="text-secondary font-medium">{r.projected_finish_date}</span>
                    {r.days_remaining_exam && ` · ${r.days_remaining_exam} days until exam`}
                  </div>
                )}

                {/* Strong / Weak topics */}
                {(r.strong_topics?.length > 0 || r.weak_topics?.length > 0) && (
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    {r.strong_topics?.length > 0 && (
                      <div>
                        <p className="text-emerald-400 text-xs font-semibold mb-2">💪 Strong Topics</p>
                        <div className="space-y-1">
                          {r.strong_topics.map((t, i) => (
                            <div key={i} className="text-xs">
                              <span className="text-secondary font-medium">{t.name}</span>
                              <span className="text-secondary/70 block">{t.reason}</span>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                    {r.weak_topics?.length > 0 && (
                      <div>
                        <p className="text-amber-400 text-xs font-semibold mb-2">⚠ Needs Attention</p>
                        <div className="space-y-1">
                          {r.weak_topics.map((t, i) => (
                            <div key={i} className="text-xs">
                              <span className="text-secondary font-medium">{t.name}</span>
                              <span className="text-secondary/70 block">{t.reason}</span>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                )}

                {/* AI summary */}
                <div className="border-t border-secondary pt-4">
                  <p className="text-secondary text-sm leading-relaxed whitespace-pre-line">{r.ai_summary}</p>
                </div>

                {/* Key recommendation */}
                {r.key_recommendation && (
                  <div className="bg-indigo-500/10 border border-indigo-500/30 rounded-lg p-3">
                    <p className="text-indigo-300 text-xs font-semibold mb-1">🎯 Key Action for Next Week</p>
                    <p className="text-secondary text-sm">{r.key_recommendation}</p>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </AppLayout>
  )
}

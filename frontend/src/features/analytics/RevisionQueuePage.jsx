import { useParams, Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { analyticsService } from '../../services'
import AppLayout from '../../layouts/AppLayout'
import RevisionCard from '../../components/RevisionCard'

export default function RevisionQueuePage() {
  const { examId } = useParams()

  const { data: queue = [], isLoading: loadingQueue } = useQuery({
    queryKey: ['revision-queue', examId],
    queryFn: () => analyticsService.getRevisionQueue(examId),
    staleTime: 30_000,
  })

  const { data: upcoming = [], isLoading: loadingUpcoming } = useQuery({
    queryKey: ['upcoming-revisions', examId],
    queryFn: () => analyticsService.getUpcomingRevisions(examId),
    staleTime: 60_000,
  })

  const urgent = queue.filter(r => r.trigger_reason === 'low_confidence' || r.revision_number === 0)
  const dueToday = queue.filter(r => r.trigger_reason !== 'low_confidence' && r.revision_number !== 0)

  return (
    <AppLayout>
      <div className="max-w-2xl mx-auto">
        <div className="flex items-start justify-between mb-6 flex-wrap gap-4">
          <div>
            <Link to={`/exams/${examId}/dashboard`} className="text-secondary/70 hover:text-secondary text-sm mb-1 block transition-colors">
              ← Dashboard
            </Link>
            <h1 className="text-2xl font-bold text-secondary">Revision Queue</h1>
            <p className="text-secondary/70 text-sm mt-1">Spaced revisions — {queue.length} due today</p>
          </div>
        </div>

        {loadingQueue ? (
          <div className="flex justify-center py-16">
            <div className="w-8 h-8 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin" />
          </div>
        ) : queue.length === 0 ? (
          <div className="card text-center py-12">
            <p className="text-4xl mb-3">✅</p>
            <h3 className="text-secondary font-semibold mb-2">All caught up!</h3>
            <p className="text-secondary/70 text-sm">No revisions due today. Keep studying and revisions will appear here when topics are due.</p>
          </div>
        ) : (
          <div className="space-y-6">
            {/* Urgent section */}
            {urgent.length > 0 && (
              <div>
                <h2 className="text-red-400 text-sm font-semibold uppercase tracking-wide mb-3 flex items-center gap-1">
                  ⚡ Urgent ({urgent.length})
                </h2>
                <div className="space-y-3">
                  {urgent.map(r => <RevisionCard key={r.id} revision={r} examId={examId} />)}
                </div>
              </div>
            )}

            {/* Due today section */}
            {dueToday.length > 0 && (
              <div>
                <h2 className="text-secondary text-sm font-semibold uppercase tracking-wide mb-3">
                  Due Today ({dueToday.length})
                </h2>
                <div className="space-y-3">
                  {dueToday.map(r => <RevisionCard key={r.id} revision={r} examId={examId} />)}
                </div>
              </div>
            )}
          </div>
        )}

        {/* Upcoming section */}
        {upcoming.length > 0 && (
          <div className="mt-8">
            <h2 className="text-secondary/70 text-sm font-semibold uppercase tracking-wide mb-3">
              Coming Up (next 7 days)
            </h2>
            {loadingUpcoming ? null : (
              <div className="space-y-2">
                {upcoming.map(r => (
                  <div key={r.id} className="flex items-center justify-between py-2.5 px-4 bg-tan rounded-lg border border-secondary">
                    <div>
                      <span className="text-secondary text-sm font-medium">{r.topic_name}</span>
                      <span className="text-slate-600 text-xs ml-2">{r.revision_label}</span>
                    </div>
                    <div className="text-right text-xs text-secondary/70">
                      <div>{r.scheduled_date}</div>
                      <div>in {r.days_until}d</div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* How spaced repetition works */}
        <div className="mt-8 card bg-tan/50">
          <h3 className="text-secondary text-sm font-semibold mb-2">📖 How Spaced Repetition Works</h3>
          <p className="text-secondary/70 text-xs leading-relaxed">
            When you complete a topic, we automatically schedule 5 revision sessions at increasing intervals:
            <span className="text-secondary/70"> 1 day → 3 days → 7 days → 15 days → 30 days.</span>
            {' '}If you feel shaky (confidence 1-2), an urgent revision is added the next day.
            Completing all 5 revisions means the topic is firmly in long-term memory.
          </p>
          <div className="flex gap-2 mt-3 flex-wrap">
            {['Day 1', 'Day 3', 'Day 7', 'Day 15', 'Day 30'].map((d, i) => (
              <div key={i} className="flex items-center gap-1">
                <div className="w-2 h-2 rounded-full bg-indigo-500" />
                <span className="text-secondary/70 text-xs">{d}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </AppLayout>
  )
}

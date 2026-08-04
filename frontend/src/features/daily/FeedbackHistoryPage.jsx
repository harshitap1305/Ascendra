import { useParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { dailyService } from '../../services'
import AppLayout from '../../layouts/AppLayout'
import FeedbackCard from '../../components/FeedbackCard'

export default function FeedbackHistoryPage() {
  const { examId } = useParams()

  const { data: history, isLoading } = useQuery({
    queryKey: ['feedback-history', examId],
    queryFn: () => dailyService.feedbackHistory(examId).then((r) => r.data),
  })

  return (
    <AppLayout>
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-white">Feedback History</h1>
        <p className="text-slate-400 text-sm mt-1">All mentor feedback from your daily check-ins</p>
      </div>

      {isLoading && (
        <div className="space-y-3">
          {[...Array(3)].map((_, i) => (
            <div key={i} className="card h-24 animate-pulse" />
          ))}
        </div>
      )}

      {!isLoading && (!history || history.length === 0) && (
        <div className="card text-center py-16">
          <p className="text-3xl mb-3">📋</p>
          <p className="text-white font-medium">No feedback yet</p>
          <p className="text-slate-400 text-sm mt-1">Submit your first daily check-in to receive mentor feedback</p>
        </div>
      )}

      {history?.length > 0 && (
        <div className="space-y-4">
          {history.map((item) => (
            <FeedbackCard
              key={item.id}
              feedback={item}
              planAdjusted={item.plan_adjusted}
              adjustmentSummary={item.adjustment_summary}
              showDate={true}
            />
          ))}
        </div>
      )}
    </AppLayout>
  )
}

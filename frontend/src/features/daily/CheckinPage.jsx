import { useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useMutation } from '@tanstack/react-query'
import { dailyService } from '../../services'
import AppLayout from '../../layouts/AppLayout'
import FeedbackCard from '../../components/FeedbackCard'

export default function CheckinPage() {
  const { examId, moduleId } = useParams()
  const navigate = useNavigate()
  const [text, setText] = useState('')
  const [planId, setPlanId] = useState(null)
  const [feedback, setFeedback] = useState(null)
  const [loadingPlan, setLoadingPlan] = useState(false)

  // Fetch today's plan to get planId
  const fetchPlan = async () => {
    setLoadingPlan(true)
    try {
      const res = await dailyService.getToday(moduleId)
      setPlanId(res.data.id)
    } catch {
      setPlanId(null)
    } finally {
      setLoadingPlan(false)
    }
  }

  // Fetch plan if not loaded yet
  if (!planId && !loadingPlan && !feedback) {
    fetchPlan()
  }

  const checkinMutation = useMutation({
    mutationFn: () => dailyService.checkin(planId, text),
    onSuccess: (res) => {
      setFeedback(res.data)
    },
  })

  const handleSubmit = () => {
    if (!planId || text.trim().length < 10) return
    checkinMutation.mutate()
  }

  const isLoading = checkinMutation.isPending
  const charCount = text.trim().length

  return (
    <AppLayout>
      <div className="max-w-2xl mx-auto">
        <div className="mb-6">
          <h1 className="text-2xl font-bold text-secondary">End-of-Day Check-in</h1>
          <p className="text-secondary/70 text-sm mt-1">
            Write freely — what did you study today? Mention tasks, questions solved, videos watched, any issues.
          </p>
        </div>

        {!feedback ? (
          <>
            <div className="card mb-4">
              <textarea
                id="checkin-textarea"
                value={text}
                onChange={(e) => setText(e.target.value)}
                placeholder="e.g. Today I watched Gate Smashers videos 4-6 on Semaphores. Solved about 20 PYQs but couldn't finish the Deadlock chapter — got distracted with college work. Feeling okay about Processes overall."
                className="w-full bg-transparent text-secondary text-sm placeholder-slate-600 resize-none focus:outline-none leading-relaxed"
                rows={8}
                disabled={isLoading}
              />
              <div className="flex items-center justify-between mt-3 pt-3 border-t border-secondary">
                <span className={`text-xs ${charCount < 10 ? 'text-slate-600' : 'text-secondary/70'}`}>
                  {charCount} chars {charCount < 10 ? `(${10 - charCount} more to enable)` : ''}
                </span>
                {isLoading && (
                  <span className="text-indigo-400 text-xs animate-pulse">
                    🧠 Analyzing your progress…
                  </span>
                )}
              </div>
            </div>

            {checkinMutation.isError && (
              <div className="mb-4 p-3 rounded-lg border border-red-500/30 bg-red-500/10 text-red-400 text-sm">
                Something went wrong. Please try again.
              </div>
            )}

            <div className="flex gap-3">
              <button
                onClick={() => navigate(`/exams/${examId}/modules/${moduleId}/today`)}
                className="btn-secondary text-sm"
              >
                ← Today's Plan
              </button>
              <button
                id="submit-checkin-btn"
                onClick={handleSubmit}
                disabled={isLoading || charCount < 10 || !planId}
                className="btn-primary flex-1 disabled:opacity-40 disabled:cursor-not-allowed"
              >
                {isLoading ? (
                  <span className="flex items-center justify-center gap-2">
                    <span className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                    Generating feedback…
                  </span>
                ) : 'Submit Check-in'}
              </button>
            </div>
          </>
        ) : (
          <div className="space-y-4">
            <FeedbackCard feedback={feedback.feedback} planAdjusted={feedback.plan_adjusted} adjustmentSummary={feedback.adjustment_summary} />
            <div className="flex gap-3 mt-6">
              <button
                onClick={() => navigate(`/exams/${examId}/modules`)}
                className="btn-secondary text-sm"
              >
                All Modules
              </button>
              <button
                onClick={() => navigate(`/exams/${examId}/feedback`)}
                className="btn-secondary text-sm"
              >
                Feedback History
              </button>
            </div>
          </div>
        )}
      </div>
    </AppLayout>
  )
}

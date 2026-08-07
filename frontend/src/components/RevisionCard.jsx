import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Frown, Meh, Smile, SmilePlus, Target } from 'lucide-react'
import { analyticsService } from '../services'

const CONFIDENCE_LABELS = ['', 'Confused', 'Shaky', 'Okay', 'Good', 'Nailed it!']
const CONFIDENCE_COLORS = ['', '#ef4444', '#f97316', '#eab308', '#34d399', '#10b981']

export default function RevisionCard({ revision, examId }) {
  const queryClient = useQueryClient()
  const [showDoneForm, setShowDoneForm] = useState(false)
  const [rating, setRating] = useState(null)
  const [showReRevisionPrompt, setShowReRevisionPrompt] = useState(false)
  const [doneRevisionId, setDoneRevisionId] = useState(null)

  const completeMutation = useMutation({
    mutationFn: () => analyticsService.completeRevision(revision.id, rating),
    onSuccess: (data) => {
      queryClient.invalidateQueries(['revision-queue', examId])
      queryClient.invalidateQueries(['dashboard', examId])
      setShowDoneForm(false)
      if (data.show_re_revision_prompt) {
        setDoneRevisionId(revision.id)
        setShowReRevisionPrompt(true)
      }
    },
  })

  const reRevisionMutation = useMutation({
    mutationFn: () => analyticsService.requestReRevision(revision.id),
    onSuccess: () => {
      setShowReRevisionPrompt(false)
      queryClient.invalidateQueries(['revision-queue', examId])
    },
  })

  const skipMutation = useMutation({
    mutationFn: () => analyticsService.skipRevision(revision.id),
    onSuccess: () => queryClient.invalidateQueries(['revision-queue', examId]),
  })

  const isUrgent = revision.trigger_reason === 'low_confidence' || revision.revision_number === 0
  const isOverdue = revision.days_overdue > 0

  return (
    <div className={`card ${isUrgent ? 'border-red-500/30 bg-red-500/5' : ''}`}>
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1 flex-wrap">
            {isUrgent && (
              <span className="badge-high text-xs">⚡ Urgent</span>
            )}
            <span className="text-xs text-secondary/70 bg-tan px-2 py-0.5 rounded-full">
              {revision.revision_label}
            </span>
            {isOverdue && (
              <span className="badge-high text-xs">{revision.days_overdue}d overdue</span>
            )}
          </div>
          <h4 className="text-secondary font-semibold truncate">{revision.topic_name}</h4>
          {revision.module_name && (
            <p className="text-secondary/70 text-xs mt-0.5">{revision.module_name}</p>
          )}
        </div>
        <div className="flex gap-2 shrink-0">
          <button
            onClick={() => skipMutation.mutate()}
            disabled={skipMutation.isPending}
            className="text-secondary/70 hover:text-secondary text-sm px-2 py-1 rounded transition-colors"
          >
            Skip
          </button>
          <button
            id={`done-revision-${revision.id}`}
            onClick={() => setShowDoneForm(v => !v)}
            className="btn-primary text-sm py-1"
          >
            Done ✓
          </button>
        </div>
      </div>

      {/* Confidence rating form */}
      {showDoneForm && (
        <div className="mt-3 pt-3 border-t border-secondary">
          <p className="text-secondary/70 text-xs mb-2">How confident do you feel? (optional)</p>
          <div className="flex gap-2 mb-3 flex-wrap">
            {[1, 2, 3, 4, 5].map(r => (
              <button
                key={r}
                onClick={() => setRating(r === rating ? null : r)}
                className={`flex flex-col items-center px-2 py-1.5 rounded-lg border text-xs transition-all ${
                  rating === r
                    ? 'border-indigo-500 bg-indigo-500/20 text-secondary'
                    : 'border-secondary text-secondary/70 hover:border-slate-500'
                }`}
              >
                <span className="text-base flex items-center justify-center">{r === 1 ? <Frown size={16} /> : r === 2 ? <Meh size={16} /> : r === 3 ? <Smile size={16} /> : r === 4 ? <SmilePlus size={16} /> : <Target size={16} />}</span>
                <span>{CONFIDENCE_LABELS[r]}</span>
              </button>
            ))}
          </div>
          <button
            onClick={() => completeMutation.mutate()}
            disabled={completeMutation.isPending}
            className="btn-primary text-sm w-full"
          >
            {completeMutation.isPending ? 'Saving…' : 'Mark Complete'}
          </button>
        </div>
      )}

      {/* Re-revision prompt — shown when user rates ≤ 2 */}
      {showReRevisionPrompt && (
        <div className="mt-3 pt-3 border-t border-secondary bg-amber-500/10 rounded-lg p-3">
          <p className="text-amber-400 text-sm font-medium">Still a bit shaky? 🤔</p>
          <p className="text-secondary/70 text-xs mt-1 mb-3">
            You rated your confidence low. Would you like to schedule another revision for tomorrow?
          </p>
          <div className="flex gap-2">
            <button
              onClick={() => reRevisionMutation.mutate()}
              disabled={reRevisionMutation.isPending}
              className="btn-primary text-sm flex-1"
            >
              {reRevisionMutation.isPending ? 'Scheduling…' : 'Yes, schedule one more'}
            </button>
            <button
              onClick={() => setShowReRevisionPrompt(false)}
              className="btn-secondary text-sm"
            >
              No thanks
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

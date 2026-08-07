import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { dailyService, analyticsService } from '../../services'
import AppLayout from '../../layouts/AppLayout'
import RevisionCard from '../../components/RevisionCard'

const TYPE_CONFIG = {
  study: { icon: '📖', label: 'Study', color: 'text-blue-400' },
  practice: { icon: '✏️', label: 'Practice', color: 'text-purple-400' },
  revision: { icon: '🔄', label: 'Revision', color: 'text-emerald-400' },
  carry_over: { icon: '↩️', label: 'Carry-over', color: 'text-amber-400' },
}

export default function TodayPage() {
  const { examId, moduleId } = useParams()
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  const { data: plan, isLoading, error } = useQuery({
    queryKey: ['today-plan', moduleId],
    queryFn: () => dailyService.getToday(moduleId).then((r) => r.data),
    retry: 1,
  })

  const [checkedTasks, setCheckedTasks] = useState({})

  useEffect(() => {
    if (plan?.id) {
      try {
        const saved = JSON.parse(localStorage.getItem(`checked_tasks_${plan.id}`)) || {}
        setCheckedTasks(saved)
      } catch {
        setCheckedTasks({})
      }
    }
  }, [plan?.id])

  const toggleTask = (taskKey) => {
    setCheckedTasks((prev) => {
      const next = { ...prev, [taskKey]: !prev[taskKey] }
      if (plan?.id) {
        try {
          localStorage.setItem(`checked_tasks_${plan.id}`, JSON.stringify(next))
        } catch {
          // Ignore localStorage errors
        }
      }
      return next
    })
  }

  const { data: revisionQueue = [] } = useQuery({
    queryKey: ['revision-queue', examId],
    queryFn: () => analyticsService.getRevisionQueue(examId),
    staleTime: 30_000,
    enabled: !!examId,
  })

  const skipMutation = useMutation({
    mutationFn: () => dailyService.skipToday(plan.id),
    onSuccess: () => {
      queryClient.invalidateQueries(['today-plan', moduleId])
    },
  })

  if (isLoading) {
    return (
      <AppLayout>
        <div className="flex items-center justify-center h-48">
          <div className="w-8 h-8 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin" />
        </div>
      </AppLayout>
    )
  }

  if (error || !plan) {
    return (
      <AppLayout>
        <div className="card text-center py-16">
          <p className="text-3xl mb-3">🎉</p>
          <p className="text-secondary font-semibold text-lg">No plan scheduled for today</p>
          <p className="text-secondary/70 text-sm mt-2">Your module window has ended, or you've completed all planned days!</p>
          <button
            onClick={() => navigate(`/exams/${examId}/modules`)}
            className="btn-primary mt-6"
          >
            Back to Modules
          </button>
        </div>
      </AppLayout>
    )
  }

  const isCompleted = plan.status === 'completed'
  const isSkipped = plan.status === 'skipped'
  const allTasks = [...(plan.carry_over_tasks || []), ...(plan.tasks || [])]
  const grouped = groupByType(allTasks)

  return (
    <AppLayout>
      {/* Header */}
      <div className="flex items-start justify-between mb-6 flex-wrap gap-4">
        <div>
          <p className="text-secondary/70 text-sm mb-1">
            {new Date(plan.plan_date).toLocaleDateString('en-IN', { weekday: 'long', day: 'numeric', month: 'long' })}
          </p>
          <h1 className="text-2xl font-bold text-secondary">Today's Plan</h1>
          {plan.daily_goal && (
            <p className="text-secondary/70 text-sm mt-1 italic">"{plan.daily_goal}"</p>
          )}
        </div>
        <div className="flex items-center gap-2">
          <span className={`text-xs px-3 py-1 rounded-full font-medium border
            ${isCompleted ? 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30'
              : isSkipped ? 'bg-slate-600/40 text-secondary/70 border-secondary'
              : 'bg-amber-500/20 text-amber-400 border-amber-500/30'}`}
          >
            {isCompleted ? '✓ Completed' : isSkipped ? 'Skipped' : '⏳ In Progress'}
          </span>
          <span className="text-secondary/70 text-sm">{plan.planned_hours}h planned</span>
        </div>
      </div>

      {/* Carry-over notice */}
      {plan.carry_over_tasks?.length > 0 && (
        <div className="mb-4 p-3 rounded-lg border border-amber-500/30 bg-amber-500/10">
          <p className="text-amber-400 text-sm font-medium">
            ↩️ {plan.carry_over_tasks.length} task(s) carried over from yesterday
          </p>
        </div>
      )}

      {/* Task list */}
      <div className="space-y-4 mb-8">
        {Object.entries(grouped).map(([type, tasks]) => {
          const cfg = TYPE_CONFIG[type] || TYPE_CONFIG.study
          return (
            <div key={type}>
              <p className={`text-xs font-semibold uppercase tracking-wider mb-2 ${cfg.color}`}>
                {cfg.icon} {cfg.label}
              </p>
              <div className="space-y-2">
                {tasks.map((task, i) => {
                  const taskKey = `${type}-${i}-${task.description}`
                  const isChecked = isCompleted || !!checkedTasks[taskKey]
                  return (
                    <div
                      key={taskKey}
                      onClick={() => toggleTask(taskKey)}
                      className={`card py-3 px-4 flex items-start gap-3 cursor-pointer transition-all duration-200 hover:border-secondary select-none ${
                        isChecked ? 'bg-tan/40 border-emerald-500/30' : ''
                      }`}
                    >
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation()
                          toggleTask(taskKey)
                        }}
                        className={`w-5 h-5 rounded border flex items-center justify-center flex-shrink-0 mt-0.5 transition-all ${
                          isChecked
                            ? 'bg-emerald-500 border-emerald-500 text-secondary shadow-sm shadow-emerald-500/30'
                            : 'border-secondary bg-tan/80 hover:border-slate-400'
                        }`}
                      >
                        {isChecked && <span className="text-xs font-bold leading-none">✓</span>}
                      </button>
                      <div className="flex-1">
                        <p className={`text-sm transition-colors ${isChecked ? 'text-secondary/70 line-through' : 'text-secondary font-medium'}`}>
                          {task.description}
                        </p>
                        {task.resource_detail && (
                          <p className={`text-xs mt-0.5 ${isChecked ? 'text-slate-600' : 'text-secondary/70'}`}>
                            {task.resource_detail}
                          </p>
                        )}
                      </div>
                      <span className={`text-xs shrink-0 font-mono px-2 py-0.5 rounded ${
                        isChecked ? 'bg-tan/50 text-secondary/70' : 'bg-tan text-secondary'
                      }`}>
                        {task.estimated_hours}h
                      </span>
                    </div>
                  )
                })}
              </div>
            </div>
          )
        })}
      </div>

      {/* Today's Revisions Section */}
      {revisionQueue.length > 0 && (
        <div className="mb-8">
          <p className="text-xs font-semibold uppercase tracking-wider mb-3 text-emerald-400">
            🔄 Today's Revisions ({revisionQueue.length} due)
          </p>
          <div className="space-y-3">
            {revisionQueue.map((r) => (
              <RevisionCard key={r.id} revision={r} examId={examId} />
            ))}
          </div>
        </div>
      )}

      {/* Actions */}
      {!isCompleted && !isSkipped && (
        <div className="flex gap-3">
          <button
            id="go-to-checkin-btn"
            onClick={() => navigate(`/exams/${examId}/modules/${moduleId}/checkin`)}
            className="btn-primary flex-1"
          >
            ✏️ Submit Check-in
          </button>
          <button
            id="skip-today-btn"
            onClick={() => skipMutation.mutate()}
            disabled={skipMutation.isPending}
            className="btn-secondary text-sm"
          >
            {skipMutation.isPending ? '...' : 'Skip Today'}
          </button>
        </div>
      )}

      {isCompleted && (
        <div className="card text-center py-6">
          <p className="text-emerald-400 font-semibold">✓ Check-in submitted</p>
          <button
            onClick={() => navigate(`/exams/${examId}/feedback`)}
            className="btn-secondary text-sm mt-3"
          >
            View Feedback
          </button>
        </div>
      )}

      {isSkipped && (
        <div className="card py-4 text-center">
          <p className="text-secondary/70 text-sm">Day skipped — tasks carry over to tomorrow.</p>
        </div>
      )}
    </AppLayout>
  )
}

function groupByType(tasks) {
  const order = ['carry_over', 'study', 'practice', 'revision']
  const grouped = {}
  for (const task of tasks) {
    const t = task.type || 'study'
    if (!grouped[t]) grouped[t] = []
    grouped[t].push(task)
  }
  return Object.fromEntries(order.filter((k) => grouped[k]).map((k) => [k, grouped[k]]))
}

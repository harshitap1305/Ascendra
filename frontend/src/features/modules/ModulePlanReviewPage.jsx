import { useState } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { moduleService } from '../../services'
import AppLayout from '../../layouts/AppLayout'
import DayPlanCard from '../../components/DayPlanCard'
import ResourceList from '../../components/ResourceList'

export default function ModulePlanReviewPage() {
  const { examId, moduleId } = useParams()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [activeTab, setActiveTab] = useState('plan') // plan | resources

  const { data: detail, isLoading } = useQuery({
    queryKey: ['module-detail', moduleId],
    queryFn: () => moduleService.getDetail(moduleId).then((r) => r.data),
    refetchInterval: (query) => {
      // Keep polling if still planning
      if (query.state.data?.module_start?.status === 'planning') return 2000
      return false
    },
  })

  const retryMutation = useMutation({
    mutationFn: () => moduleService.retryPlan(moduleId),
    onSuccess: () => queryClient.invalidateQueries(['module-detail', moduleId]),
  })

  const acceptMutation = useMutation({
    mutationFn: () => moduleService.acceptPlan(moduleId),
    onSuccess: () => {
      queryClient.invalidateQueries(['module-detail', moduleId])
      navigate(`/exams/${examId}/modules`)
    },
  })

  const updateDayMutation = useMutation({
    mutationFn: ({ dayId, data }) => moduleService.updateDay(moduleId, dayId, data),
    onSuccess: () => queryClient.invalidateQueries(['module-detail', moduleId]),
  })

  const ms = detail?.module_start
  const plan = detail?.plan
  const resources = detail?.resources || []

  if (isLoading) {
    return (
      <AppLayout>
        <div className="flex items-center justify-center py-32">
          <div className="w-10 h-10 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin" />
        </div>
      </AppLayout>
    )
  }

  const isPlanReady = ms?.status === 'active' && plan
  const isFailed = ms?.status === 'planning_failed'
  const isPlanning = ms?.status === 'planning'

  return (
    <AppLayout>
      <div className="max-w-3xl mx-auto">
        {/* Header */}
        <div className="flex items-start justify-between mb-6 flex-wrap gap-4">
          <div>
            <button
              onClick={() => navigate(`/exams/${examId}/modules`)}
              className="text-slate-500 hover:text-slate-300 text-sm mb-1 transition-colors"
            >
              ← All Modules
            </button>
            <h1 className="text-2xl font-bold text-white">
              {isPlanReady ? `${plan.total_days}-Day Master Plan` : 'Module Plan'}
            </h1>
            {plan?.summary && (
              <p className="text-slate-400 text-sm mt-1 max-w-xl">{plan.summary}</p>
            )}
          </div>
          <div className="flex gap-3">
            {isFailed && (
              <button
                id="retry-plan-btn"
                onClick={() => retryMutation.mutate()}
                disabled={retryMutation.isPending}
                className="btn-secondary text-sm"
              >
                {retryMutation.isPending ? 'Retrying…' : '🔄 Retry Plan'}
              </button>
            )}
            {isPlanReady && !plan.is_accepted && (
              <button
                id="accept-plan-btn"
                onClick={() => acceptMutation.mutate()}
                disabled={acceptMutation.isPending}
                className="btn-primary text-sm"
              >
                {acceptMutation.isPending ? 'Accepting…' : '✅ Accept Plan'}
              </button>
            )}
            {plan?.is_accepted && (
              <>
                <span className="bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 text-sm px-3 py-1.5 rounded-lg font-medium">
                  ✓ Plan Accepted
                </span>
                <Link
                  to={`/exams/${examId}/modules/${moduleId}/today`}
                  className="btn-primary text-sm"
                >
                  📅 Today's Plan
                </Link>
              </>
            )}
          </div>
        </div>

        {/* Status states */}
        {isPlanning && (
          <div className="card flex items-center gap-4 py-8">
            <div className="w-8 h-8 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin shrink-0" />
            <div>
              <p className="text-white font-medium">Building your plan…</p>
              <p className="text-slate-400 text-sm">AI is processing. This page updates automatically.</p>
            </div>
          </div>
        )}

        {isFailed && (
          <div className="card bg-red-500/5 border-red-500/30 mb-6">
            <div className="flex items-start gap-3">
              <span className="text-2xl">⚠️</span>
              <div>
                <p className="font-medium text-red-300">Plan generation failed</p>
                {ms?.error_detail && (
                  <p className="text-sm text-red-400/80 mt-1">{ms.error_detail}</p>
                )}
                <p className="text-sm text-slate-400 mt-2">
                  Your resources were saved. Hit "Retry Plan" to regenerate without re-parsing resources.
                </p>
              </div>
            </div>
          </div>
        )}

        {/* Tabs */}
        {(isPlanReady || resources.length > 0) && (
          <>
            <div className="flex gap-1 bg-slate-900 border border-slate-800 rounded-lg p-1 mb-6 w-fit">
              {['plan', 'resources'].map((tab) => (
                <button
                  key={tab}
                  onClick={() => setActiveTab(tab)}
                  className={`px-4 py-1.5 rounded-md text-sm font-medium capitalize transition-all
                    ${activeTab === tab
                      ? 'bg-indigo-600 text-white'
                      : 'text-slate-400 hover:text-slate-200'
                    }`}
                >
                  {tab === 'plan' ? `📅 Plan (${plan?.total_days || 0} days)` : `📦 Resources (${resources.length})`}
                </button>
              ))}
            </div>

            {/* Plan tab */}
            {activeTab === 'plan' && isPlanReady && (
              <div className="space-y-3">
                <div className="flex items-center justify-between text-xs text-slate-500 mb-4">
                  <span>
                    {plan.total_days} days · {ms?.daily_hours_available}h/day budget
                    {ms?.expected_hours && ` · ~${ms.expected_hours}h total`}
                  </span>
                  {!plan.is_accepted && (
                    <span className="text-indigo-400">Click hours to adjust • Accept when ready</span>
                  )}
                </div>
                {plan.days.map((day) => (
                  <DayPlanCard
                    key={day.id}
                    day={day}
                    editable={!plan.is_accepted}
                    onUpdate={(dayId, data) => updateDayMutation.mutate({ dayId, data })}
                  />
                ))}
              </div>
            )}

            {/* Resources tab */}
            {activeTab === 'resources' && (
              <div className="card">
                <h2 className="font-semibold text-white mb-4">
                  Extracted Resources
                </h2>
                <ResourceList resources={resources} />
              </div>
            )}
          </>
        )}
      </div>
    </AppLayout>
  )
}

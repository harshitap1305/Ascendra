import { useParams, useNavigate, Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { moduleService, examService } from '../../services'
import AppLayout from '../../layouts/AppLayout'

const STATUS_STYLES = {
  planning: { pill: 'bg-amber-500/20 text-amber-400 border-amber-500/30', label: 'Planning…' },
  active: { pill: 'bg-indigo-500/20 text-indigo-400 border-indigo-500/30', label: 'Active' },
  planning_failed: { pill: 'bg-red-500/20 text-red-400 border-red-500/30', label: 'Failed' },
  completed: { pill: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30', label: 'Completed' },
  paused: { pill: 'bg-slate-600/40 text-secondary/70 border-secondary', label: 'Paused' },
}

export default function ModuleListPage() {
  const { examId } = useParams()
  const navigate = useNavigate()

  const { data: exam } = useQuery({
    queryKey: ['exam', examId],
    queryFn: () => examService.get(examId).then((r) => r.data),
  })

  const { data: modules, isLoading } = useQuery({
    queryKey: ['exam-modules', examId],
    queryFn: () => moduleService.listByExam(examId).then((r) => r.data),
  })

  const activeModules = modules?.filter((m) => m.status === 'active') || []
  const otherModules = modules?.filter((m) => m.status !== 'active') || []

  return (
    <AppLayout>
      <div className="flex items-start justify-between mb-8 flex-wrap gap-4">
        <div>
          <p className="text-secondary/70 text-sm mb-1">
            <Link to={`/exams/${examId}`} className="hover:text-secondary">
              {exam?.name}
            </Link>
          </p>
          <h1 className="text-2xl font-bold text-secondary">Modules</h1>
          <p className="text-secondary/70 text-sm mt-1">
            Each module is a planned topic with a day-by-day study schedule
          </p>
        </div>
        <button
          id="start-module-btn"
          onClick={() => navigate(`/exams/${examId}/modules/new`)}
          className="btn-primary"
        >
          + Start Module
        </button>
      </div>

      {isLoading && (
        <div className="space-y-3">
          {[...Array(3)].map((_, i) => (
            <div key={i} className="card h-20 animate-pulse" />
          ))}
        </div>
      )}

      {!isLoading && modules?.length === 0 && (
        <div className="card text-center py-20">
          <p className="text-4xl mb-4">🗓</p>
          <p className="text-secondary font-medium text-lg">No modules yet</p>
          <p className="text-secondary/70 text-sm mt-1 mb-6">
            Pick a topic from your syllabus and let AI build a study schedule
          </p>
          <button
            onClick={() => navigate(`/exams/${examId}/modules/new`)}
            className="btn-primary"
          >
            Start First Module
          </button>
        </div>
      )}

      {/* Active modules */}
      {activeModules.length > 0 && (
        <div className="mb-8">
          <h2 className="text-sm font-semibold text-secondary/70 uppercase tracking-wider mb-3">
            Active
          </h2>
          <div className="space-y-3">
            {activeModules.map((m) => (
              <ModuleCard key={m.id} module={m} examId={examId} />
            ))}
          </div>
        </div>
      )}

      {/* Past / other modules */}
      {otherModules.length > 0 && (
        <div>
          <h2 className="text-sm font-semibold text-secondary/70 uppercase tracking-wider mb-3">
            {activeModules.length > 0 ? 'History' : 'All Modules'}
          </h2>
          <div className="space-y-3">
            {otherModules.map((m) => (
              <ModuleCard key={m.id} module={m} examId={examId} />
            ))}
          </div>
        </div>
      )}
    </AppLayout>
  )
}

function ModuleCard({ module: m, examId }) {
  const navigate = useNavigate()
  const style = STATUS_STYLES[m.status] || STATUS_STYLES.active

  const startedDate = new Date(m.started_at).toLocaleDateString('en-IN', {
    day: 'numeric', month: 'short', year: 'numeric',
  })

  return (
    <button
      onClick={() => navigate(`/exams/${examId}/modules/${m.id}/plan`)}
      className="card w-full text-left hover:border-indigo-500/40 transition-all group"
    >
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1 min-w-0">
          <p className="font-semibold text-secondary group-hover:text-indigo-300 transition-colors truncate">
            {m.topic_name}
          </p>
          <div className="flex items-center gap-3 mt-1 text-xs text-secondary/70">
            <span>Started {startedDate}</span>
            <span>·</span>
            <span>{m.daily_hours_available}h/day</span>
          </div>
        </div>
        <span className={`text-xs px-2.5 py-1 rounded-full border font-medium shrink-0 ${style.pill}`}>
          {style.label}
        </span>
      </div>
    </button>
  )
}

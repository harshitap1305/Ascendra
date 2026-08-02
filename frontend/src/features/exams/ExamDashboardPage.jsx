import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useParams, useNavigate } from 'react-router-dom'
import { examService } from '../../services'
import AppLayout from '../../layouts/AppLayout'
import TopicTree from '../../components/TopicTree'
import ProgressBar from '../../components/ProgressBar'

export default function ExamDashboardPage() {
  const { examId } = useParams()
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  const { data: exam } = useQuery({
    queryKey: ['exam', examId],
    queryFn: () => examService.get(examId).then(r => r.data),
  })

  const { data: summary } = useQuery({
    queryKey: ['exam-summary', examId],
    queryFn: () => examService.summary(examId).then(r => r.data),
  })

  const { data: topics, isLoading: topicsLoading } = useQuery({
    queryKey: ['topics', examId],
    queryFn: () => examService.topics(examId).then(r => r.data),
  })

  const enrichMutation = useMutation({
    mutationFn: () => examService.enrich(examId),
    onSuccess: () => {
      setTimeout(() => queryClient.invalidateQueries(['topics', examId]), 15000)
    },
  })

  const anyEnriched = topics?.some(t => t.difficulty)
  const allEnriched = topics?.length > 0 && topics.every(t => t.difficulty)

  return (
    <AppLayout>
      {/* Header */}
      <div className="flex items-start justify-between mb-6 flex-wrap gap-4">
        <div>
          <p className="text-slate-500 text-sm mb-1">Exam</p>
          <h1 className="text-2xl font-bold text-white">{exam?.name || '…'}</h1>
          {exam?.goal_score && (
            <p className="text-slate-400 text-sm mt-1">Goal: {exam.goal_score}</p>
          )}
        </div>
        <div className="flex gap-3">
          <button
            onClick={() => navigate(`/exams/${examId}/syllabus`)}
            className="btn-secondary text-sm"
          >
            Edit Syllabus
          </button>
          {!allEnriched && (
            <button
              id="enrich-btn"
              onClick={() => enrichMutation.mutate()}
              disabled={enrichMutation.isPending || enrichMutation.isSuccess}
              className="btn-primary text-sm"
            >
              {enrichMutation.isPending || enrichMutation.isSuccess
                ? '⏳ Enriching…'
                : '✨ Enrich Topics'}
            </button>
          )}
        </div>
      </div>

      {/* Progress summary */}
      {summary && (
        <div className="card mb-6">
          <div className="flex items-center justify-between mb-3">
            <span className="text-sm font-medium text-slate-300">Overall Progress</span>
            <span className="text-sm font-bold text-indigo-400">{summary.progress_pct}%</span>
          </div>
          <ProgressBar pct={summary.progress_pct} />
          <div className="flex gap-6 mt-3 text-xs text-slate-500">
            <span>{summary.completed_leaf_topics} / {summary.total_leaf_topics} topics completed</span>
          </div>
        </div>
      )}

      {/* Topic tree */}
      <div className="card">
        <h2 className="font-semibold text-white mb-4">Syllabus</h2>
        {topicsLoading ? (
          <div className="space-y-2">
            {[...Array(5)].map((_, i) => (
              <div key={i} className="h-8 bg-slate-800 rounded animate-pulse" style={{ width: `${70 + i * 5}%` }} />
            ))}
          </div>
        ) : topics?.length === 0 ? (
          <div className="text-center py-10 text-slate-400">
            <p className="mb-3">No topics yet.</p>
            <button onClick={() => navigate(`/exams/${examId}/syllabus`)} className="btn-primary text-sm">
              Add Syllabus
            </button>
          </div>
        ) : (
          <TopicTree topics={topics} readOnly />
        )}
      </div>
    </AppLayout>
  )
}

import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useParams, useNavigate } from 'react-router-dom'
import { examService, topicService, syllabusService } from '../../services'
import AppLayout from '../../layouts/AppLayout'
import TopicTree from '../../components/TopicTree'

export default function SyllabusReviewPage() {
  const { examId } = useParams()
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  const [newSyllabus, setNewSyllabus] = useState('')
  const [parsing, setParsing] = useState(false)
  const [parseError, setParseError] = useState('')

  const { data: exam } = useQuery({
    queryKey: ['exam', examId],
    queryFn: () => examService.get(examId).then((r) => r.data),
  })

  const { data: topics, isLoading: topicsLoading } = useQuery({
    queryKey: ['topics', examId],
    queryFn: () => examService.topics(examId).then((r) => r.data),
  })

  const updateMutation = useMutation({
    mutationFn: ({ id, data }) => topicService.update(id, data),
    onSuccess: () => queryClient.invalidateQueries(['topics', examId]),
  })

  const deleteMutation = useMutation({
    mutationFn: (id) => topicService.delete(id),
    onSuccess: () => queryClient.invalidateQueries(['topics', examId]),
  })

  const enrichMutation = useMutation({
    mutationFn: () => examService.enrich(examId),
    onSuccess: () => {
      // Navigate straight to dashboard after triggering enrich
      navigate(`/exams/${examId}`)
    },
  })

  // Support re-uploading syllabus if they want to override
  const uploadMutation = useMutation({
    mutationFn: () => examService.uploadSyllabus(examId, newSyllabus),
    onSuccess: async (res) => {
      const uid = res.data.upload_id
      await syllabusService.parse(uid)
      setParsing(true)
      setParseError('')
      pollStatus(uid)
    },
  })

  const pollStatus = (uid) => {
    const interval = setInterval(async () => {
      try {
        const res = await syllabusService.getUploadStatus(uid)
        if (res.data.parsed_status === 'success') {
          clearInterval(interval)
          setParsing(false)
          setNewSyllabus('')
          queryClient.invalidateQueries(['topics', examId])
        } else if (res.data.parsed_status === 'failed') {
          clearInterval(interval)
          setParsing(false)
          setParseError('AI parsing failed. Please adjust the text and try again.')
        }
      } catch {
        clearInterval(interval)
        setParsing(false)
      }
    }, 2000)
  }

  const handleUpdate = (id, data) => updateMutation.mutate({ id, data })
  const handleDelete = (id) => deleteMutation.mutate(id)

  return (
    <AppLayout>
      <div className="flex items-start justify-between mb-6 flex-wrap gap-4">
        <div>
          <p className="text-slate-500 text-sm mb-1">
            {exam ? `${exam.name} • Syllabus Review` : 'Syllabus Review'}
          </p>
          <h1 className="text-2xl font-bold text-white">Review & Edit Topic Tree</h1>
          <p className="text-slate-400 text-sm mt-1">
            Review the structure AI generated. Edit titles or remove extra nodes before enriching with difficulty and study time estimation.
          </p>
        </div>
        <div className="flex gap-3">
          <button
            onClick={() => navigate(`/exams/${examId}`)}
            className="btn-secondary text-sm"
          >
            ← Dashboard
          </button>
          {topics?.length > 0 && (
            <button
              id="confirm-enrich-btn"
              onClick={() => enrichMutation.mutate()}
              disabled={enrichMutation.isPending}
              className="btn-primary text-sm"
            >
              {enrichMutation.isPending ? 'Starting…' : '✨ Confirm & Enrich →'}
            </button>
          )}
        </div>
      </div>

      {topicsLoading ? (
        <div className="card space-y-3">
          {[...Array(6)].map((_, i) => (
            <div
              key={i}
              className="h-8 bg-slate-800 rounded animate-pulse"
              style={{ width: `${65 + (i % 3) * 10}%` }}
            />
          ))}
        </div>
      ) : topics?.length === 0 ? (
        <div className="card space-y-5">
          <div className="text-center py-6">
            <p className="text-3xl mb-2">📋</p>
            <h3 className="text-lg font-medium text-white">No Syllabus Uploaded Yet</h3>
            <p className="text-slate-400 text-sm mt-1 max-w-md mx-auto">
              Paste your exam syllabus below and let our AI structure it into topics, subtopics, and chapters automatically.
            </p>
          </div>

          {parseError && (
            <div className="bg-red-500/10 border border-red-500/30 text-red-400 text-sm rounded-lg px-4 py-3">
              {parseError}
            </div>
          )}

          {parsing ? (
            <div className="py-12 flex flex-col items-center gap-4">
              <div className="w-10 h-10 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin" />
              <p className="text-slate-400 text-sm">AI is analyzing and organizing your syllabus…</p>
              <p className="text-slate-600 text-xs">This usually takes 10–30 seconds</p>
            </div>
          ) : (
            <>
              <textarea
                className="input min-h-64 font-mono text-sm leading-relaxed"
                placeholder={`Engineering Mathematics\n  Linear Algebra\n    Matrices\n    Eigen Values\n  Calculus\n    Limits\n    Integration`}
                value={newSyllabus}
                onChange={(e) => setNewSyllabus(e.target.value)}
              />
              <button
                className="btn-primary w-full"
                disabled={!newSyllabus.trim() || uploadMutation.isPending}
                onClick={() => uploadMutation.mutate()}
              >
                {uploadMutation.isPending ? 'Uploading…' : '🤖 Structure with AI'}
              </button>
            </>
          )}
        </div>
      ) : (
        <div className="card">
          <div className="flex items-center justify-between mb-4 pb-3 border-b border-slate-800">
            <span className="text-sm font-semibold text-slate-300">
              Interactive Outline (Click to expand/collapse, hover to edit)
            </span>
            <span className="text-xs text-slate-500">
              Changes save instantly
            </span>
          </div>
          <TopicTree
            topics={topics}
            readOnly={false}
            onUpdate={handleUpdate}
            onDelete={handleDelete}
          />
        </div>
      )}
    </AppLayout>
  )
}

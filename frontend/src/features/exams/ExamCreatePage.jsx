import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useMutation } from '@tanstack/react-query'
import { examService, syllabusService } from '../../services'
import AppLayout from '../../layouts/AppLayout'

const STEPS = ['Exam Details', 'Paste Syllabus']

export default function ExamCreatePage() {
  const navigate = useNavigate()
  const [step, setStep] = useState(0)
  const [examId, setExamId] = useState(null)
  const [uploadId, setUploadId] = useState(null)
  const [syllabus, setSyllabus] = useState('')
  const [parsing, setParsing] = useState(false)
  const [parseError, setParseError] = useState('')

  const [form, setForm] = useState({
    name: '',
    description: '',
    exam_date: '',
    daily_study_hours: 4,
    experience_level: 'beginner',
    goal_score: '',
  })

  // Step 1: Create exam
  const createMutation = useMutation({
    mutationFn: () => examService.create({
      ...form,
      daily_study_hours: Number(form.daily_study_hours),
      exam_date: form.exam_date || null,
      description: form.description || null,
      goal_score: form.goal_score || null,
    }),
    onSuccess: (res) => {
      setExamId(res.data.id)
      setStep(1)
    },
  })

  // Step 2a: Upload syllabus text
  const uploadMutation = useMutation({
    mutationFn: () => examService.uploadSyllabus(examId, syllabus),
    onSuccess: async (res) => {
      const uid = res.data.upload_id
      setUploadId(uid)
      // Trigger parse
      await syllabusService.parse(uid)
      setParsing(true)
      // Poll for status
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
          navigate(`/exams/${examId}/syllabus`)
        } else if (res.data.parsed_status === 'failed') {
          clearInterval(interval)
          setParsing(false)
          setParseError('AI parsing failed. Please try again or simplify your syllabus text.')
        }
      } catch {
        clearInterval(interval)
        setParsing(false)
        setParseError('Connection error while polling. Please check the syllabus page.')
      }
    }, 2000)
  }

  return (
    <AppLayout>
      <div className="max-w-2xl mx-auto">
        {/* Step indicator */}
        <div className="flex items-center gap-3 mb-8">
          {STEPS.map((s, i) => (
            <div key={s} className="flex items-center gap-2">
              <div className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold
                ${i === step ? 'bg-indigo-600 text-secondary' : i < step ? 'bg-emerald-600 text-secondary' : 'bg-tan text-secondary/70'}`}>
                {i < step ? '✓' : i + 1}
              </div>
              <span className={`text-sm font-medium ${i === step ? 'text-secondary' : 'text-secondary/70'}`}>{s}</span>
              {i < STEPS.length - 1 && <div className="w-8 h-px bg-slate-700 ml-1" />}
            </div>
          ))}
        </div>

        {/* Step 1: Exam details */}
        {step === 0 && (
          <div className="card space-y-5">
            <h2 className="text-lg font-semibold text-secondary">Exam Details</h2>

            {createMutation.isError && (
              <div className="bg-red-500/10 border border-red-500/30 text-red-400 text-sm rounded-lg px-4 py-3">
                {createMutation.error?.response?.data?.detail || 'Failed to create exam'}
              </div>
            )}

            <div>
              <label className="label">Exam Name *</label>
              <input className="input" placeholder="e.g. GATE CS 2027"
                value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value }))} required />
            </div>

            <div>
              <label className="label">Description</label>
              <input className="input" placeholder="Optional short description"
                value={form.description} onChange={e => setForm(f => ({ ...f, description: e.target.value }))} />
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="label">Exam Date</label>
                <input type="date" className="input"
                  value={form.exam_date} onChange={e => setForm(f => ({ ...f, exam_date: e.target.value }))} />
              </div>
              <div>
                <label className="label">Daily Study Hours</label>
                <input type="number" min="0.5" max="16" step="0.5" className="input"
                  value={form.daily_study_hours} onChange={e => setForm(f => ({ ...f, daily_study_hours: e.target.value }))} />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="label">Experience Level</label>
                <select className="input" value={form.experience_level}
                  onChange={e => setForm(f => ({ ...f, experience_level: e.target.value }))}>
                  <option value="beginner">Beginner</option>
                  <option value="intermediate">Intermediate</option>
                  <option value="revision">Revision Stage</option>
                </select>
              </div>
              <div>
                <label className="label">Goal / Target Score</label>
                <input className="input" placeholder="e.g. AIR under 500"
                  value={form.goal_score} onChange={e => setForm(f => ({ ...f, goal_score: e.target.value }))} />
              </div>
            </div>

            <button
              id="create-exam-next"
              className="btn-primary w-full"
              disabled={!form.name || createMutation.isPending}
              onClick={() => createMutation.mutate()}
            >
              {createMutation.isPending ? 'Creating…' : 'Continue →'}
            </button>
          </div>
        )}

        {/* Step 2: Paste syllabus */}
        {step === 1 && (
          <div className="card space-y-5">
            <div>
              <h2 className="text-lg font-semibold text-secondary">Paste Your Syllabus</h2>
              <p className="text-sm text-secondary/70 mt-1">
                Paste raw syllabus text — copy-pasted from PDF is fine. AI will structure it.
              </p>
            </div>

            {parseError && (
              <div className="bg-red-500/10 border border-red-500/30 text-red-400 text-sm rounded-lg px-4 py-3">
                {parseError}
              </div>
            )}

            {parsing ? (
              <div className="py-16 flex flex-col items-center gap-4">
                <div className="w-10 h-10 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin" />
                <p className="text-secondary/70 text-sm">AI is parsing your syllabus…</p>
                <p className="text-slate-600 text-xs">This usually takes 10–30 seconds</p>
              </div>
            ) : (
              <>
                <textarea
                  id="syllabus-textarea"
                  className="input min-h-72 resize-y font-mono text-sm leading-relaxed"
                  placeholder={`Engineering Mathematics\n  Linear Algebra\n    Matrices\n    Eigen Values\n  Calculus\n    Limits\n    Integration`}
                  value={syllabus}
                  onChange={e => setSyllabus(e.target.value)}
                />
                <button
                  id="parse-syllabus-btn"
                  className="btn-primary w-full"
                  disabled={!syllabus.trim() || uploadMutation.isPending}
                  onClick={() => uploadMutation.mutate()}
                >
                  {uploadMutation.isPending ? 'Uploading…' : '🤖 Parse with AI →'}
                </button>
              </>
            )}
          </div>
        )}
      </div>
    </AppLayout>
  )
}

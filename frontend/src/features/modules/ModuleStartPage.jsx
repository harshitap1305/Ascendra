import { useState, useEffect, useRef } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { examService, moduleService } from '../../services'
import AppLayout from '../../layouts/AppLayout'
import TopicTree from '../../components/TopicTree'

export default function ModuleStartPage() {
  const { examId } = useParams()
  const navigate = useNavigate()

  const [selectedTopic, setSelectedTopic] = useState(null)
  const [rawInput, setRawInput] = useState('')
  const [dailyHours, setDailyHours] = useState(4)
  const [expectedHours, setExpectedHours] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [polling, setPolling] = useState(false)
  const [error, setError] = useState('')
  const pollingRef = useRef(null)

  const { data: exam } = useQuery({
    queryKey: ['exam', examId],
    queryFn: () => examService.get(examId).then((r) => r.data),
  })

  const { data: topics } = useQuery({
    queryKey: ['topics', examId],
    queryFn: () => examService.topics(examId).then((r) => r.data),
  })

  // Clean up polling on unmount
  useEffect(() => () => { if (pollingRef.current) clearInterval(pollingRef.current) }, [])

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!selectedTopic) { setError('Please select a topic from the tree'); return }
    if (rawInput.trim().length < 10) { setError('Please describe your resources and plan'); return }

    setError('')
    setSubmitting(true)

    try {
      const res = await moduleService.start({
        topic_id: selectedTopic.id,
        raw_input: rawInput.trim(),
        daily_hours_available: parseFloat(dailyHours),
        expected_hours: expectedHours ? parseFloat(expectedHours) : null,
      })
      const moduleId = res.data.module_start_id
      setSubmitting(false)
      setPolling(true)

      // Start polling
      pollingRef.current = setInterval(async () => {
        try {
          const statusRes = await moduleService.getStatus(moduleId)
          const { status, error_detail } = statusRes.data
          if (status === 'active') {
            clearInterval(pollingRef.current)
            navigate(`/exams/${examId}/modules/${moduleId}/plan`)
          } else if (status === 'planning_failed') {
            clearInterval(pollingRef.current)
            setPolling(false)
            setError(error_detail || 'Planning failed. You can retry from the module page.')
            navigate(`/exams/${examId}/modules/${moduleId}/plan`)
          }
        } catch {
          clearInterval(pollingRef.current)
          setPolling(false)
          setError('Lost connection while waiting. Check the module page.')
        }
      }, 2000)
    } catch (err) {
      setSubmitting(false)
      setError(err.response?.data?.detail || 'Failed to start module. Please try again.')
    }
  }

  return (
    <AppLayout>
      <div className="max-w-4xl mx-auto">
        <div className="mb-8">
          <p className="text-slate-500 text-sm mb-1">{exam?.name}</p>
          <h1 className="text-2xl font-bold text-white">Start a Module</h1>
          <p className="text-slate-400 text-sm mt-1">
            Pick a topic and describe your resources. AI will build a day-by-day plan.
          </p>
        </div>

        {polling ? (
          <div className="card flex flex-col items-center py-20 gap-5">
            <div className="w-14 h-14 border-4 border-indigo-500 border-t-transparent rounded-full animate-spin" />
            <div className="text-center">
              <p className="text-white font-semibold text-lg">Building your plan…</p>
              <p className="text-slate-400 text-sm mt-1">
                AI is parsing your resources and planning day by day
              </p>
              <p className="text-slate-600 text-xs mt-2">This usually takes 15–30 seconds</p>
            </div>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Left: Topic selection */}
            <div className="card">
              <h2 className="font-semibold text-white mb-1">
                Select Topic
                {selectedTopic && (
                  <span className="ml-2 text-sm text-indigo-400 font-normal">
                    — {selectedTopic.name}
                  </span>
                )}
              </h2>
              <p className="text-xs text-slate-500 mb-4">Click any topic to select it</p>

              {topics && topics.length > 0 ? (
                <div className="max-h-80 overflow-y-auto pr-1">
                  <TopicTreeSelectable
                    topics={topics}
                    selectedId={selectedTopic?.id}
                    onSelect={setSelectedTopic}
                  />
                </div>
              ) : (
                <p className="text-slate-500 text-sm">No topics yet — add a syllabus first.</p>
              )}
            </div>

            {/* Right: Input form */}
            <div className="card space-y-5">
              <h2 className="font-semibold text-white">Your Plan</h2>

              {error && (
                <div className="bg-red-500/10 border border-red-500/30 text-red-400 text-sm rounded-lg px-4 py-3">
                  {error}
                </div>
              )}

              <div>
                <label className="label">Resources & Study Plan</label>
                <textarea
                  id="module-raw-input"
                  className="input min-h-36 text-sm leading-relaxed resize-none"
                  placeholder={`Example:\nWatch Gate Smashers OS playlist (45 videos)\nRead Galvin chapters 1-5\nSolve 200 PYQs from GATE Overflow\nExpect around 20 hours total`}
                  value={rawInput}
                  onChange={(e) => setRawInput(e.target.value)}
                  required
                />
                <p className="text-xs text-slate-500 mt-1">
                  Just write naturally — AI will extract and structure everything.
                </p>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="label">Daily Hours Available</label>
                  <input
                    type="number" min="0.5" max="20" step="0.5"
                    className="input"
                    value={dailyHours}
                    onChange={(e) => setDailyHours(e.target.value)}
                  />
                </div>
                <div>
                  <label className="label">Expected Total Hours</label>
                  <input
                    type="number" min="1" max="500" step="0.5"
                    className="input"
                    placeholder="Optional"
                    value={expectedHours}
                    onChange={(e) => setExpectedHours(e.target.value)}
                  />
                </div>
              </div>

              <button
                id="start-module-btn"
                type="submit"
                disabled={submitting || !selectedTopic || rawInput.trim().length < 10}
                className="btn-primary w-full"
              >
                {submitting ? 'Starting…' : '🚀 Generate Master Plan'}
              </button>
            </div>
          </form>
        )}
      </div>
    </AppLayout>
  )
}

// Selectable variant of TopicTree (simplified — click on any node to select)
function TopicTreeSelectable({ topics, selectedId, onSelect }) {
  return (
    <div className="space-y-0.5">
      {topics.map((topic) => (
        <SelectableNode
          key={topic.id}
          topic={topic}
          selectedId={selectedId}
          onSelect={onSelect}
          depth={0}
        />
      ))}
    </div>
  )
}

function SelectableNode({ topic, selectedId, onSelect, depth }) {
  const [expanded, setExpanded] = useState(true)
  const isSelected = topic.id === selectedId
  const hasChildren = topic.children && topic.children.length > 0

  return (
    <div>
      <div
        className={`flex items-center gap-2 px-2 py-1.5 rounded-lg cursor-pointer text-sm transition-all
          ${isSelected
            ? 'bg-indigo-600/20 border border-indigo-500/40 text-indigo-300'
            : 'hover:bg-slate-800/60 text-slate-300 border border-transparent'
          }`}
        style={{ paddingLeft: `${8 + depth * 16}px` }}
        onClick={() => onSelect(topic)}
      >
        {hasChildren && (
          <button
            className="text-slate-500 hover:text-slate-300 shrink-0 w-3"
            onClick={(e) => { e.stopPropagation(); setExpanded(!expanded) }}
          >
            {expanded ? '▼' : '▶'}
          </button>
        )}
        {!hasChildren && <span className="text-slate-600 w-3 shrink-0">•</span>}
        <span className="truncate">{topic.name}</span>
        {isSelected && <span className="ml-auto text-indigo-400 text-xs shrink-0">✓</span>}
      </div>
      {hasChildren && expanded && (
        <div>
          {topic.children.map((child) => (
            <SelectableNode
              key={child.id}
              topic={child}
              selectedId={selectedId}
              onSelect={onSelect}
              depth={depth + 1}
            />
          ))}
        </div>
      )}
    </div>
  )
}

import { useState } from 'react'
import { Video, BookOpen, PenTool, RefreshCw, Link as LinkIcon, Clock, Target, Book, LayoutList } from 'lucide-react'

const STATUS_STYLES = {
  pending: 'bg-slate-700/50 text-secondary/70 border-secondary',
  done: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30',
  skipped: 'bg-slate-700/30 text-secondary/70 border-secondary',
  adjusted: 'bg-amber-500/10 text-amber-400 border-amber-500/30',
}

const RESOURCE_ICONS = { 
  video: <Video size={14} />, 
  book: <BookOpen size={14} />, 
  practice: <PenTool size={14} />, 
  revision: <RefreshCw size={14} />, 
  other: <LinkIcon size={14} /> 
}

export default function DayPlanCard({ day, editable = false, onUpdate }) {
  const [isExpanded, setIsExpanded] = useState(false)
  const [editingHours, setEditingHours] = useState(false)
  const [hours, setHours] = useState(day.planned_hours)

  const handleHoursSave = () => {
    setEditingHours(false)
    if (hours !== day.planned_hours && onUpdate) {
      onUpdate(day.id, { planned_hours: parseFloat(hours) })
    }
  }

  return (
    <div className={`border rounded-xl overflow-hidden transition-all duration-200 ${STATUS_STYLES[day.status] || STATUS_STYLES.pending}`}>
      {/* Header — always visible */}
      <button
        className="w-full flex items-center justify-between px-4 py-3 text-left hover:bg-white/5 transition-colors"
        onClick={() => setIsExpanded(!isExpanded)}
      >
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-full bg-indigo-600/20 border border-indigo-500/30 flex items-center justify-center text-sm font-bold text-indigo-400">
            {day.day_number}
          </div>
          <div>
            <p className="font-medium text-secondary text-sm">
              {day.focus_topics.slice(0, 2).join(' · ')}
              {day.focus_topics.length > 2 && ` +${day.focus_topics.length - 2} more`}
            </p>
            <p className="text-xs text-secondary/70 mt-0.5">{day.planned_date}</p>
          </div>
        </div>
        <div className="flex items-center gap-3 shrink-0">
          {editingHours ? (
            <input
              type="number"
              step="0.5"
              min="0.5"
              max="20"
              className="input w-20 py-1 text-sm text-center"
              value={hours}
              onChange={(e) => setHours(e.target.value)}
              onBlur={handleHoursSave}
              onKeyDown={(e) => e.key === 'Enter' && handleHoursSave()}
              onClick={(e) => e.stopPropagation()}
              autoFocus
            />
          ) : (
            <div
              className={`text-sm font-mono px-2 py-1 rounded ${editable ? 'hover:bg-white/10 cursor-pointer' : 'cursor-default'} transition-colors`}
              onClick={(e) => { if (editable) { e.stopPropagation(); setEditingHours(true) } }}
              title={editable ? "Click to edit hours" : ""}
            >
              <Clock size={14} className="inline mr-1" /> {day.planned_hours}h
            </div>
          )}
          <span className="text-xs capitalize px-2 py-0.5 rounded-full bg-current/10 opacity-70">
            {day.status}
          </span>
          <span className="text-secondary/70 text-xs">{isExpanded ? '▲' : '▼'}</span>
        </div>
      </button>

      {/* Expanded details */}
      {isExpanded && (
        <div className="px-4 pb-4 border-t border-current/20 pt-3 space-y-3">
          {day.goals && (
            <div className="bg-indigo-500/5 border border-indigo-500/20 rounded-lg px-3 py-2">
              <p className="text-xs font-semibold text-indigo-400 mb-1 flex items-center gap-1.5"><Target size={14} /> Today's Goal</p>
              <p className="text-sm text-secondary">{day.goals}</p>
            </div>
          )}

          {day.focus_topics.length > 0 && (
            <div>
              <p className="text-xs font-semibold text-secondary/70 mb-1.5 flex items-center gap-1.5"><Book size={14} /> Topics to cover</p>
              <div className="flex flex-wrap gap-1.5">
                {day.focus_topics.map((t, i) => (
                  <span key={i} className="text-xs bg-tan border border-secondary text-secondary px-2 py-0.5 rounded-full">
                    {t}
                  </span>
                ))}
              </div>
            </div>
          )}

          {day.planned_resources?.length > 0 && (
            <div>
              <p className="text-xs font-semibold text-secondary/70 mb-1.5">📋 Resources</p>
              <ul className="space-y-1">
                {day.planned_resources.map((r, i) => (
                  <li key={i} className="text-xs text-secondary/70 flex items-start gap-1.5">
                    <span>{RESOURCE_ICONS[r.type] || '•'}</span>
                    <span>{r.detail}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {day.notes && (
            <div className="bg-tan/60 rounded-lg px-3 py-2">
              <p className="text-xs font-semibold text-secondary/70 mb-1">Notes</p>
              <p className="text-xs text-secondary/70">{day.notes}</p>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

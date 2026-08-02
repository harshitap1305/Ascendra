import { useState } from 'react'

function TopicNode({ topic, readOnly, onUpdate, onDelete }) {
  const [isEditing, setIsEditing] = useState(false)
  const [name, setName] = useState(topic.name)
  const [isExpanded, setIsExpanded] = useState(true)

  const handleSave = () => {
    if (name.trim() && name !== topic.name) {
      onUpdate(topic.id, { name: name.trim() })
    }
    setIsEditing(false)
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter') handleSave()
    if (e.key === 'Escape') {
      setName(topic.name)
      setIsEditing(false)
    }
  }

  const getDifficultyBadge = (difficulty) => {
    if (!difficulty) return null
    const badgeClass = {
      low: 'badge-low',
      medium: 'badge-medium',
      high: 'badge-high',
    }[difficulty.toLowerCase()] || 'badge-medium'
    return <span className={badgeClass}>{difficulty}</span>
  }

  const hasChildren = topic.children && topic.children.length > 0

  return (
    <div className="my-1">
      <div className="flex items-center justify-between group py-2 px-3 rounded-lg hover:bg-slate-800/50 border border-transparent hover:border-slate-800 transition-all">
        <div className="flex items-center gap-2 flex-1 min-w-0">
          {hasChildren ? (
            <button
              onClick={() => setIsExpanded(!isExpanded)}
              className="w-5 h-5 flex items-center justify-center text-slate-400 hover:text-slate-200 focus:outline-none"
            >
              {isExpanded ? '▼' : '▶'}
            </button>
          ) : (
            <div className="w-5 h-5 flex items-center justify-center text-slate-600 font-mono text-xs">
              •
            </div>
          )}

          {isEditing ? (
            <div className="flex items-center gap-2 flex-1 max-w-md">
              <input
                type="text"
                className="input py-1 px-2 text-sm"
                value={name}
                onChange={(e) => setName(e.target.value)}
                onBlur={handleSave}
                onKeyDown={handleKeyDown}
                autoFocus
              />
            </div>
          ) : (
            <div className="flex items-center gap-2 truncate flex-1">
              <span className="font-medium text-slate-200 text-sm truncate">
                {topic.name}
              </span>
              {getDifficultyBadge(topic.difficulty)}
              {topic.estimated_hours != null && (
                <span className="text-xs text-slate-500 font-mono bg-slate-800/80 px-1.5 py-0.5 rounded">
                  {topic.estimated_hours}h
                </span>
              )}
              {topic.weightage != null && (
                <span className="text-xs text-indigo-400/80 font-mono bg-indigo-500/10 px-1.5 py-0.5 rounded border border-indigo-500/20">
                  {topic.weightage}%
                </span>
              )}
            </div>
          )}
        </div>

        {!readOnly && (
          <div className="opacity-0 group-hover:opacity-100 flex items-center gap-2 transition-opacity">
            {!isEditing && (
              <button
                onClick={() => setIsEditing(true)}
                className="text-xs text-slate-400 hover:text-slate-200 px-2 py-1 rounded hover:bg-slate-700/50"
              >
                Edit
              </button>
            )}
            <button
              onClick={() => onDelete(topic.id)}
              className="text-xs text-red-400/80 hover:text-red-300 px-2 py-1 rounded hover:bg-red-500/10"
            >
              Delete
            </button>
          </div>
        )}
      </div>

      {hasChildren && isExpanded && (
        <div className="pl-6 border-l border-slate-800/80 ml-2.5 mt-1 space-y-1">
          {topic.children.map((child) => (
            <TopicNode
              key={child.id}
              topic={child}
              readOnly={readOnly}
              onUpdate={onUpdate}
              onDelete={onDelete}
            />
          ))}
        </div>
      )}
    </div>
  )
}

export default function TopicTree({ topics, readOnly = false, onUpdate, onDelete }) {
  return (
    <div className="space-y-1 text-sm">
      {topics.map((topic) => (
        <TopicNode
          key={topic.id}
          topic={topic}
          readOnly={readOnly}
          onUpdate={onUpdate}
          onDelete={onDelete}
        />
      ))}
    </div>
  )
}

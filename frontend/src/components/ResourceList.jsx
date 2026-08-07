import { Video, BookOpen, PenTool, RefreshCw, Link as LinkIcon } from 'lucide-react'

const RESOURCE_ICONS = {
  video: <Video size={16} />,
  book: <BookOpen size={16} />,
  practice: <PenTool size={16} />,
  revision: <RefreshCw size={16} />,
  other: <LinkIcon size={16} />
}

const RESOURCE_LABELS = {
  video: 'Video',
  book: 'Book',
  practice: 'Practice',
  revision: 'Revision',
  other: 'Other',
}

export default function ResourceList({ resources }) {
  if (!resources || resources.length === 0) {
    return (
      <p className="text-secondary/70 text-sm italic">No resources extracted yet.</p>
    )
  }

  // Group by type
  const grouped = resources.reduce((acc, r) => {
    if (!acc[r.type]) acc[r.type] = []
    acc[r.type].push(r)
    return acc
  }, {})

  return (
    <div className="space-y-4">
      {Object.entries(grouped).map(([type, items]) => (
        <div key={type}>
          <p className="text-xs font-semibold text-secondary/70 uppercase tracking-wider mb-2">
            {RESOURCE_ICONS[type]} {RESOURCE_LABELS[type] || type}
          </p>
          <ul className="space-y-1.5">
            {items.map((r, i) => (
              <li key={i} className="flex items-start gap-3 text-sm">
                <div className="flex-1 min-w-0">
                  <span className="text-secondary font-medium">{r.title}</span>
                  {r.source_name && (
                    <span className="text-secondary/70 ml-2 text-xs">via {r.source_name}</span>
                  )}
                  {r.total_units && (
                    <span className="ml-2 text-xs text-indigo-400/80 bg-indigo-500/10 border border-indigo-500/20 px-1.5 py-0.5 rounded font-mono">
                      {r.total_units} units
                    </span>
                  )}
                </div>
                <span className="text-xs text-slate-600 shrink-0">
                  {r.units_completed}/{r.total_units || '?'} done
                </span>
              </li>
            ))}
          </ul>
        </div>
      ))}
    </div>
  )
}

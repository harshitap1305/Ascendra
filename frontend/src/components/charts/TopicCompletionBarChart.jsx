import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Cell, ResponsiveContainer,
} from 'recharts'

function statusColor(status) {
  if (status === 'completed') return '#10b981'
  if (status === 'in_progress') return '#f59e0b'
  return '#334155'
}

const CustomTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null
  const d = payload[0]?.payload
  return (
    <div className="bg-tan border border-secondary rounded-lg p-3 text-xs shadow-xl max-w-48">
      <p className="text-secondary font-semibold mb-1 truncate">{label}</p>
      <p className="text-secondary/70">Completion: <span className="text-secondary">{d?.completion_pct?.toFixed(1)}%</span></p>
      <p className="text-secondary/70">Est. hours: <span className="text-secondary">{d?.estimated_hours}h</span></p>
      <p className="text-secondary/70">Status: <span className="text-secondary capitalize">{d?.status?.replace('_', ' ')}</span></p>
    </div>
  )
}

export default function TopicCompletionBarChart({ data = [] }) {
  if (data.length === 0) {
    return (
      <div className="card h-44 flex items-center justify-center text-slate-600 text-sm">
        No topics yet — add your syllabus to see progress.
      </div>
    )
  }

  return (
    <div className="card">
      <h3 className="text-sm font-semibold text-secondary mb-4">Topic-wise Progress</h3>
      <ResponsiveContainer width="100%" height={Math.max(160, data.length * 36)}>
        <BarChart
          data={data}
          layout="vertical"
          margin={{ top: 0, right: 8, left: 0, bottom: 0 }}
          barSize={16}
        >
          <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" horizontal={false} />
          <XAxis
            type="number" domain={[0, 100]}
            tick={{ fill: '#64748b', fontSize: 11 }}
            axisLine={false} tickLine={false}
            tickFormatter={v => `${v}%`}
          />
          <YAxis
            type="category" dataKey="topic_name"
            tick={{ fill: '#94a3b8', fontSize: 11 }}
            axisLine={false} tickLine={false}
            width={110}
          />
          <Tooltip content={<CustomTooltip />} cursor={{ fill: '#1e293b' }} />
          <Bar dataKey="completion_pct" radius={[0, 4, 4, 0]}>
            {data.map((entry, i) => (
              <Cell key={i} fill={statusColor(entry.status)} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
      {/* Legend */}
      <div className="flex gap-4 mt-3 justify-end text-xs text-secondary/70">
        <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-emerald-500 inline-block" />Completed</span>
        <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-amber-500 inline-block" />In Progress</span>
        <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-slate-600 inline-block" />Not Started</span>
      </div>
    </div>
  )
}

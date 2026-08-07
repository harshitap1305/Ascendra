import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Cell, ResponsiveContainer,
} from 'recharts'

function statusColor(status) {
  if (status === 'completed') return '#10b981'
  if (status === 'in_progress') return '#f59e0b'
  return '#a5846c'
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
      <h3 className="text-sm font-semibold text-secondary mb-4 uppercase tracking-wide">Topic-wise Progress</h3>
      <ResponsiveContainer width="100%" height={Math.max(250, data.length * 45)}>
        <BarChart
          data={data}
          layout="vertical"
          margin={{ top: 0, right: 10, left: 10, bottom: 0 }}
          barSize={18}
        >
          <CartesianGrid strokeDasharray="3 3" stroke="#541A1A" strokeOpacity={0.2} horizontal={false} />
          <XAxis
            type="number" domain={[0, 100]}
            tick={{ fill: '#541A1A', fontSize: 11, fontWeight: 'bold' }}
            axisLine={false} tickLine={false}
            tickFormatter={v => `${v}%`}
          />
          <YAxis
            type="category" dataKey="topic_name"
            tick={{ fill: '#541A1A', fontSize: 11, fontWeight: 'bold' }}
            axisLine={false} tickLine={false}
            width={130}
            tickFormatter={(name) => name.length > 22 ? name.substring(0, 22) + '...' : name}
          />
          <Tooltip content={<CustomTooltip />} cursor={{ fill: 'rgba(84, 26, 26, 0.05)' }} />
          <Bar dataKey="completion_pct" radius={[0, 4, 4, 0]}>
            {data.map((entry, i) => (
              <Cell key={i} fill={statusColor(entry.status)} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
      {/* Legend */}
      <div className="flex gap-4 mt-4 justify-end text-xs text-secondary font-bold">
        <span className="flex items-center gap-1.5"><span className="w-3 h-3 rounded bg-[#10b981] border-2 border-secondary" />Completed</span>
        <span className="flex items-center gap-1.5"><span className="w-3 h-3 rounded bg-[#f59e0b] border-2 border-secondary" />In Progress</span>
        <span className="flex items-center gap-1.5"><span className="w-3 h-3 rounded bg-[#a5846c] border-2 border-secondary" />Not Started</span>
      </div>
    </div>
  )
}

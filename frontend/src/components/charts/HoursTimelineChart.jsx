import { useState } from 'react'
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend,
} from 'recharts'
import { format, parseISO } from 'date-fns'

const RANGE_OPTIONS = [
  { label: 'This Week', days: 7 },
  { label: 'This Month', days: 30 },
  { label: 'All Time', days: 365 },
]

const CustomTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null
  const planned = payload.find(p => p.dataKey === 'planned')?.value ?? 0
  const actual = payload.find(p => p.dataKey === 'actual')?.value ?? 0
  const delta = actual - planned
  return (
    <div className="bg-slate-900 border border-slate-700 rounded-lg p-3 text-xs shadow-xl">
      <p className="text-slate-300 font-medium mb-1">{label}</p>
      <p className="text-slate-400">Planned: <span className="text-slate-200">{planned}h</span></p>
      <p className="text-slate-400">Actual:  <span className="text-slate-200">{actual}h</span></p>
      <p className={`font-semibold mt-1 ${delta >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
        {delta >= 0 ? '+' : ''}{delta.toFixed(1)}h vs plan
      </p>
    </div>
  )
}

export default function HoursTimelineChart({ data = [], onRangeChange }) {
  const [selected, setSelected] = useState(1) // index into RANGE_OPTIONS, default 30-day

  const handleRange = (i) => {
    setSelected(i)
    onRangeChange?.(RANGE_OPTIONS[i].days)
  }

  const chartData = data.map(d => ({
    date: format(parseISO(d.date), 'MMM d'),
    planned: d.planned,
    actual: d.actual,
  }))

  return (
    <div className="card">
      <div className="flex items-center justify-between mb-4 flex-wrap gap-2">
        <h3 className="text-sm font-semibold text-slate-200">Hours Studied vs Planned</h3>
        <div className="flex gap-1 bg-slate-800 rounded-lg p-0.5">
          {RANGE_OPTIONS.map((opt, i) => (
            <button
              key={opt.label}
              onClick={() => handleRange(i)}
              className={`px-3 py-1 text-xs rounded-md transition-all font-medium ${
                selected === i
                  ? 'bg-indigo-600 text-white'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              {opt.label}
            </button>
          ))}
        </div>
      </div>

      {chartData.length === 0 ? (
        <div className="h-44 flex items-center justify-center text-slate-600 text-sm">
          No study data yet — start your first check-in to see your timeline.
        </div>
      ) : (
        <ResponsiveContainer width="100%" height={200}>
          <AreaChart data={chartData} margin={{ top: 4, right: 4, left: -20, bottom: 0 }}>
            <defs>
              <linearGradient id="gradPlanned" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#64748b" stopOpacity={0.3} />
                <stop offset="95%" stopColor="#64748b" stopOpacity={0} />
              </linearGradient>
              <linearGradient id="gradActual" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#6366f1" stopOpacity={0.4} />
                <stop offset="95%" stopColor="#6366f1" stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
            <XAxis
              dataKey="date"
              tick={{ fill: '#64748b', fontSize: 11 }}
              axisLine={false}
              tickLine={false}
              interval="preserveStartEnd"
            />
            <YAxis
              tick={{ fill: '#64748b', fontSize: 11 }}
              axisLine={false}
              tickLine={false}
              tickFormatter={v => `${v}h`}
            />
            <Tooltip content={<CustomTooltip />} />
            <Legend
              iconType="line"
              formatter={v => <span style={{ color: '#94a3b8', fontSize: 11 }}>{v}</span>}
            />
            <Area
              type="monotone"
              dataKey="planned"
              name="Planned"
              stroke="#475569"
              strokeDasharray="5 3"
              strokeWidth={1.5}
              fill="url(#gradPlanned)"
              dot={false}
            />
            <Area
              type="monotone"
              dataKey="actual"
              name="Actual"
              stroke="#6366f1"
              strokeWidth={2}
              fill="url(#gradActual)"
              dot={false}
              activeDot={{ r: 4, strokeWidth: 0, fill: '#818cf8' }}
            />
          </AreaChart>
        </ResponsiveContainer>
      )}
    </div>
  )
}

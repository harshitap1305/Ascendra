// Reusable KPI stat card used across the dashboard
export default function StatCard({ label, value, icon, subtext, trend, trendUp }) {
  return (
    <div className="card flex flex-col gap-2 min-w-0">
      <div className="flex items-center justify-between">
        <span className="text-secondary/70 text-xs font-medium uppercase tracking-wider">{label}</span>
        {icon && <span className="text-xl">{icon}</span>}
      </div>
      <div className="text-2xl font-bold text-secondary truncate">{value ?? '—'}</div>
      {subtext && <div className="text-secondary/70 text-xs">{subtext}</div>}
      {trend && (
        <div className={`text-xs font-medium ${trendUp ? 'text-emerald-400' : 'text-red-400'}`}>
          {trendUp ? '▲' : '▼'} {trend}
        </div>
      )}
    </div>
  )
}

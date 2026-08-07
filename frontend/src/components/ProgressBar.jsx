export default function ProgressBar({ pct }) {
  return (
    <div className="w-full bg-tan rounded-full h-2.5 overflow-hidden">
      <div
        className="bg-indigo-600 h-2.5 rounded-full transition-all duration-500 ease-out"
        style={{ width: `${Math.min(Math.max(pct || 0, 0), 100)}%` }}
      />
    </div>
  )
}

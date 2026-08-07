import { Link } from 'react-router-dom'

const EXPERIENCE_LABELS = {
  beginner: 'Beginner',
  intermediate: 'Intermediate',
  revision: 'Revision',
}

export default function ExamCard({ exam }) {
  const daysLeft = exam.exam_date
    ? Math.ceil((new Date(exam.exam_date) - new Date()) / (1000 * 60 * 60 * 24))
    : null

  return (
    <Link
      to={`/exams/${exam.id}`}
      id={`exam-card-${exam.id}`}
      className="card hover:border-indigo-500/50 hover:shadow-indigo-500/5 transition-all duration-200 group block"
    >
      <div className="flex items-start justify-between mb-3">
        <div>
          <h2 className="font-semibold text-secondary group-hover:text-indigo-300 transition-colors">
            {exam.name}
          </h2>
          <span className="text-xs text-secondary/70 mt-0.5 block">
            {EXPERIENCE_LABELS[exam.experience_level] || exam.experience_level}
          </span>
        </div>
        <span className={`text-xs px-2 py-1 rounded-full font-medium ${
          exam.status === 'active'
            ? 'bg-emerald-500/20 text-emerald-400'
            : 'bg-slate-700 text-secondary/70'
        }`}>
          {exam.status}
        </span>
      </div>

      {exam.description && (
        <p className="text-sm text-secondary/70 mb-3 line-clamp-2">{exam.description}</p>
      )}

      <div className="flex items-center gap-4 text-xs text-secondary/70 mt-auto pt-3 border-t border-secondary">
        <span>📅 {daysLeft !== null ? `${daysLeft}d left` : 'No date set'}</span>
        <span>⏱ {exam.daily_study_hours}h/day</span>
      </div>
    </Link>
  )
}

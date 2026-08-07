import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { Book } from 'lucide-react'
import { examService } from '../../services'
import AppLayout from '../../layouts/AppLayout'
import ExamCard from './ExamCard'

export default function ExamListPage() {
  const { data, isLoading, isError } = useQuery({
    queryKey: ['exams'],
    queryFn: () => examService.list().then(r => r.data),
  })

  return (
    <AppLayout>
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold text-secondary">My Exams</h1>
          <p className="text-secondary/70 text-sm mt-1">Track your preparation across all exams</p>
        </div>
        <Link to="/exams/new" id="create-exam-btn" className="btn-primary">
          + New Exam
        </Link>
      </div>

      {isLoading && (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {[...Array(3)].map((_, i) => (
            <div key={i} className="card h-44 animate-pulse bg-tan" />
          ))}
        </div>
      )}

      {isError && (
        <div className="card text-center py-12 text-secondary/70">
          Failed to load exams. Please refresh.
        </div>
      )}

      {data?.length === 0 && (
        <div className="card text-center py-20">
          <div className="flex justify-center text-secondary mb-4"><Book size={40} /></div>
          <p className="text-secondary font-medium text-lg">No exams yet</p>
          <p className="text-secondary/70 text-sm mt-1 mb-6">Create your first exam to get started</p>
          <Link to="/exams/new" className="btn-primary inline-block">
            Create Exam
          </Link>
        </div>
      )}

      {data?.length > 0 && (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {data.map(exam => (
            <ExamCard key={exam.id} exam={exam} />
          ))}
        </div>
      )}
    </AppLayout>
  )
}

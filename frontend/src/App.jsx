import { Routes, Route, Navigate } from 'react-router-dom'
import ProtectedRoute from './components/ProtectedRoute'
import LoginPage from './features/auth/LoginPage'
import SignupPage from './features/auth/SignupPage'
import ExamListPage from './features/exams/ExamListPage'
import ExamCreatePage from './features/exams/ExamCreatePage'
import ExamDashboardPage from './features/exams/ExamDashboardPage'
import SyllabusReviewPage from './features/syllabus/SyllabusReviewPage'

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/signup" element={<SignupPage />} />
      
      <Route
        path="/"
        element={
          <ProtectedRoute>
            <ExamListPage />
          </ProtectedRoute>
        }
      />
      
      <Route
        path="/exams/new"
        element={
          <ProtectedRoute>
            <ExamCreatePage />
          </ProtectedRoute>
        }
      />

      <Route
        path="/exams/:examId"
        element={
          <ProtectedRoute>
            <ExamDashboardPage />
          </ProtectedRoute>
        }
      />

      <Route
        path="/exams/:examId/syllabus"
        element={
          <ProtectedRoute>
            <SyllabusReviewPage />
          </ProtectedRoute>
        }
      />

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}

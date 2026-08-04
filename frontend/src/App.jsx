import { Routes, Route, Navigate } from 'react-router-dom'
import ProtectedRoute from './components/ProtectedRoute'
import LoginPage from './features/auth/LoginPage'
import SignupPage from './features/auth/SignupPage'
import ExamListPage from './features/exams/ExamListPage'
import ExamCreatePage from './features/exams/ExamCreatePage'
import ExamDashboardPage from './features/exams/ExamDashboardPage'
import SyllabusReviewPage from './features/syllabus/SyllabusReviewPage'
import ModuleStartPage from './features/modules/ModuleStartPage'
import ModulePlanReviewPage from './features/modules/ModulePlanReviewPage'
import ModuleListPage from './features/modules/ModuleListPage'
import TodayPage from './features/daily/TodayPage'
import CheckinPage from './features/daily/CheckinPage'
import FeedbackHistoryPage from './features/daily/FeedbackHistoryPage'

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


      <Route
        path="/exams/:examId/modules"
        element={
          <ProtectedRoute>
            <ModuleListPage />
          </ProtectedRoute>
        }
      />

      <Route
        path="/exams/:examId/modules/new"
        element={
          <ProtectedRoute>
            <ModuleStartPage />
          </ProtectedRoute>
        }
      />

      <Route
        path="/exams/:examId/modules/:moduleId/plan"
        element={
          <ProtectedRoute>
            <ModulePlanReviewPage />
          </ProtectedRoute>
        }
      />


      <Route
        path="/exams/:examId/modules/:moduleId/today"
        element={
          <ProtectedRoute>
            <TodayPage />
          </ProtectedRoute>
        }
      />

      <Route
        path="/exams/:examId/modules/:moduleId/checkin"
        element={
          <ProtectedRoute>
            <CheckinPage />
          </ProtectedRoute>
        }
      />

      <Route
        path="/exams/:examId/feedback"
        element={
          <ProtectedRoute>
            <FeedbackHistoryPage />
          </ProtectedRoute>
        }
      />

      <Route path="*" element={<Navigate to="/" replace />} />

    </Routes>
  )
}

import api from './api'

export const authService = {
  signup: (data) => api.post('/auth/signup', data),
  login: (data) => api.post('/auth/login', data),
  me: () => api.get('/auth/me'),
}

export const examService = {
  create: (data) => api.post('/exams', data),
  list: (status = 'active') => api.get('/exams', { params: { status } }),
  get: (id) => api.get(`/exams/${id}`),
  update: (id, data) => api.patch(`/exams/${id}`, data),
  delete: (id) => api.delete(`/exams/${id}`),
  summary: (id) => api.get(`/exams/${id}/summary`),
  topics: (id) => api.get(`/exams/${id}/topics`),
  enrich: (id) => api.post(`/exams/${id}/enrich-topics`),
  uploadSyllabus: (id, raw_text) => api.post(`/exams/${id}/syllabus`, { raw_text }),
  resources: (id) => api.get(`/exams/${id}/resources`),
  addResource: (id, data) => api.post(`/exams/${id}/resources`, data),
}

export const syllabusService = {
  getUploadStatus: (uploadId) => api.get(`/syllabus-uploads/${uploadId}/status`),
  parse: (uploadId) => api.post(`/syllabus-uploads/${uploadId}/parse`),
}

export const topicService = {
  update: (id, data) => api.patch(`/topics/${id}`, data),
  delete: (id) => api.delete(`/topics/${id}`),
}

export const moduleService = {
  start: (data) => api.post('/modules/start', data),
  getStatus: (id) => api.get(`/modules/${id}/status`),
  getPlan: (id) => api.get(`/modules/${id}/plan`),
  getDetail: (id) => api.get(`/modules/${id}`),
  retryPlan: (id) => api.post(`/modules/${id}/retry-plan`),
  updateDay: (moduleId, dayId, data) => api.patch(`/modules/${moduleId}/plan/days/${dayId}`, data),
  acceptPlan: (id) => api.post(`/modules/${id}/accept`),
  listByExam: (examId) => api.get(`/exams/${examId}/modules`),
}

export const dailyService = {
  getToday: (moduleStartId) => api.get('/daily/today', { params: { module_start_id: moduleStartId } }),
  getPlan: (planId) => api.get(`/daily/${planId}`),
  checkin: (planId, raw_text) => api.post(`/daily/${planId}/checkin`, { raw_text }),
  getFeedback: (planId) => api.get(`/daily/${planId}/feedback`),
  skipToday: (planId) => api.patch(`/daily/${planId}/skip`),
  listForModule: (moduleId) => api.get(`/daily/modules/${moduleId}/daily-plans`),
  feedbackHistory: (examId) => api.get(`/daily/exams/${examId}/feedback-history`),
}

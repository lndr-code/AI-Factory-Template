// Typed API client for the AI Factory backend

export interface DashboardData {
  report_content: string
  last_entry: string
  session_report: string
}

export interface Task {
  filename: string
  display_name: string
  status: 'open' | 'done' | 'failed' | 'blocked'
  path: string
}

export interface TasksData {
  tasks: Task[]
}

export interface QuestionsData {
  open_questions: string
  has_questions: boolean
  answered_questions: string
}

export type RunState = 'not_started' | 'running' | 'finished' | 'failed'

export interface RunStatus {
  state: RunState
  running: boolean
  pid: number | null
  returncode: number | null
  stdout_tail: string
}

// ---------------------------------------------------------------------------
// Core fetch helper
// ---------------------------------------------------------------------------

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, init)
  if (!res.ok) {
    let detail = `HTTP ${res.status}`
    try {
      const body = await res.json()
      detail = body.detail ?? detail
    } catch {
      // ignore parse errors
    }
    throw new Error(detail)
  }
  return res.json() as Promise<T>
}

// ---------------------------------------------------------------------------
// Endpoint wrappers
// ---------------------------------------------------------------------------

export const fetchDashboard = () => apiFetch<DashboardData>('/api/dashboard')

export const fetchTasks = () => apiFetch<TasksData>('/api/tasks')

export const fetchQuestions = () => apiFetch<QuestionsData>('/api/questions')

export const fetchRunStatus = () => apiFetch<RunStatus>('/api/run/status')

export const startRun = () =>
  apiFetch<{ started: boolean; pid: number }>('/api/run/start', { method: 'POST' })

export const submitAnswer = (answer: string) =>
  apiFetch<{ ok: boolean; questions_archived: string }>('/api/questions/answer', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ answer }),
  })

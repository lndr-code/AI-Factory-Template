import { Routes, Route, NavLink } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import Dashboard from './pages/Dashboard'
import Tasks from './pages/Tasks'
import Questions from './pages/Questions'
import { fetchRunStatus } from './api/client'

function RunIndicator() {
  const { data } = useQuery({
    queryKey: ['run-status'],
    queryFn: fetchRunStatus,
    refetchInterval: 2000,
  })

  const state = data?.state ?? 'not_started'
  const isRunning = data?.running ?? false

  const dotColor =
    state === 'running'
      ? 'bg-yellow-400 animate-pulse'
      : state === 'failed'
      ? 'bg-red-400'
      : state === 'finished'
      ? 'bg-green-400'
      : 'bg-gray-500'

  const label =
    state === 'running'
      ? 'Running'
      : state === 'failed'
      ? 'Failed'
      : state === 'finished'
      ? 'Done'
      : 'Idle'

  return (
    <div className="flex items-center gap-2 text-xs">
      <span className={`inline-block w-2 h-2 rounded-full flex-shrink-0 ${dotColor}`} />
      <span className="text-gray-400">{label}</span>
    </div>
  )
}

export default function App() {
  const navClass = ({ isActive }: { isActive: boolean }) =>
    `block px-3 py-2 rounded text-sm font-medium transition-colors ${
      isActive
        ? 'bg-gray-700 text-white'
        : 'text-gray-400 hover:text-white hover:bg-gray-700'
    }`

  return (
    <div className="flex h-screen bg-gray-900 text-white overflow-hidden">
      {/* Sidebar */}
      <aside className="w-48 flex-shrink-0 bg-gray-800 flex flex-col border-r border-gray-700">
        <div className="p-4 border-b border-gray-700">
          <h1 className="text-xs font-bold text-gray-300 uppercase tracking-widest">
            AI Factory
          </h1>
        </div>
        <nav className="flex-1 p-3 space-y-1">
          <NavLink to="/" end className={navClass}>
            Dashboard
          </NavLink>
          <NavLink to="/tasks" className={navClass}>
            Tasks
          </NavLink>
          <NavLink to="/questions" className={navClass}>
            Questions
          </NavLink>
        </nav>
        <div className="p-3 border-t border-gray-700">
          <RunIndicator />
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-auto">
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/tasks" element={<Tasks />} />
          <Route path="/questions" element={<Questions />} />
        </Routes>
      </main>
    </div>
  )
}

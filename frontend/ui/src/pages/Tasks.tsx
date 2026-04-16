import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { fetchTasks } from '../api/client'
import type { Task } from '../api/client'
import StatusBadge from '../components/StatusBadge'

type StatusFilter = 'all' | Task['status']

const FILTERS: StatusFilter[] = ['all', 'open', 'done', 'failed', 'blocked']

export default function Tasks() {
  const { data, isLoading, error } = useQuery({
    queryKey: ['tasks'],
    queryFn: fetchTasks,
    refetchInterval: 15_000,
  })

  const [filter, setFilter] = useState<StatusFilter>('all')

  const tasks = data?.tasks ?? []
  const filtered = filter === 'all' ? tasks : tasks.filter(t => t.status === filter)

  const countFor = (s: Task['status']) => tasks.filter(t => t.status === s).length

  return (
    <div className="p-6 space-y-4 max-w-3xl">
      <h1 className="text-lg font-semibold text-white">Tasks</h1>

      {/* Filter bar */}
      <div className="flex flex-wrap gap-2">
        {FILTERS.map(f => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            className={`px-3 py-1 rounded text-xs font-medium transition-colors ${
              filter === f
                ? 'bg-gray-600 text-white'
                : 'bg-gray-800 text-gray-400 hover:text-white hover:bg-gray-700'
            }`}
          >
            {f}
            <span className="ml-1 opacity-60">
              ({f === 'all' ? tasks.length : countFor(f as Task['status'])})
            </span>
          </button>
        ))}
      </div>

      {isLoading && <p className="text-gray-400 text-sm">Loading…</p>}
      {error && (
        <p className="text-red-400 text-sm">Error: {(error as Error).message}</p>
      )}

      {!isLoading && filtered.length === 0 && (
        <p className="text-gray-500 text-sm italic">No tasks found.</p>
      )}

      <div className="space-y-2">
        {filtered.map(task => (
          <div
            key={task.filename}
            className="bg-gray-800 rounded px-4 py-3 flex items-center justify-between gap-4 border border-gray-700"
          >
            <div className="min-w-0">
              <span className="text-sm text-gray-100 block truncate">
                {task.display_name}
              </span>
              <span className="text-xs text-gray-500 font-mono">
                {task.filename}
              </span>
            </div>
            <StatusBadge status={task.status} />
          </div>
        ))}
      </div>
    </div>
  )
}

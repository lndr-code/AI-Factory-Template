import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { fetchRunStatus, startRun } from '../api/client'
import type { RunState } from '../api/client'

const stateLabel: Record<RunState, string> = {
  not_started: 'No runs started yet',
  running: 'Run in progress…',
  finished: 'Last run finished successfully',
  failed: 'Last run failed',
}

export default function RunButton() {
  const queryClient = useQueryClient()
  const [error, setError] = useState<string | null>(null)

  const { data: status } = useQuery({
    queryKey: ['run-status'],
    queryFn: fetchRunStatus,
    refetchInterval: 2000,
  })

  const isRunning = status?.running ?? false
  const state = status?.state ?? 'not_started'

  const handleStart = async () => {
    setError(null)
    try {
      await startRun()
      queryClient.invalidateQueries({ queryKey: ['run-status'] })
      queryClient.invalidateQueries({ queryKey: ['dashboard'] })
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to start run')
    }
  }

  return (
    <div className="space-y-2">
      <button
        onClick={handleStart}
        disabled={isRunning}
        className={`px-4 py-2 rounded font-medium text-sm transition-colors ${
          isRunning
            ? 'bg-gray-600 text-gray-400 cursor-not-allowed'
            : 'bg-blue-600 hover:bg-blue-500 text-white'
        }`}
      >
        {isRunning ? (
          <span className="flex items-center gap-2">
            <span className="inline-block w-3 h-3 border-2 border-white border-t-transparent rounded-full animate-spin" />
            Running…
          </span>
        ) : (
          'Start Next Iteration'
        )}
      </button>

      <p className={`text-xs ${state === 'failed' ? 'text-red-400' : 'text-gray-500'}`}>
        {stateLabel[state]}
        {status?.returncode != null ? ` (exit ${status.returncode})` : ''}
      </p>

      {error && (
        <p className="text-red-400 text-xs mt-1">{error}</p>
      )}
    </div>
  )
}

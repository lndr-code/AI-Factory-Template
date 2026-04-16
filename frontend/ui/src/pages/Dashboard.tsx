import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { fetchDashboard, fetchRunStatus } from '../api/client'
import ReportViewer from '../components/ReportViewer'
import RunButton from '../components/RunButton'

function RunOutput() {
  const { data } = useQuery({
    queryKey: ['run-status'],
    queryFn: fetchRunStatus,
    refetchInterval: 2000,
  })

  if (!data || data.state === 'not_started' || !data.stdout_tail) return null

  return (
    <ReportViewer
      content={data.stdout_tail}
      title="Run Output"
      maxHeight="24vh"
      scrollToBottom
    />
  )
}

export default function Dashboard() {
  const { data, isLoading, error } = useQuery({
    queryKey: ['dashboard'],
    queryFn: fetchDashboard,
    refetchInterval: 15_000,
  })

  const [showSession, setShowSession] = useState(false)

  return (
    <div className="p-6 space-y-6 max-w-4xl">
      {/* Header */}
      <div className="flex items-start justify-between gap-6">
        <div>
          <h1 className="text-lg font-semibold text-white">Dashboard</h1>
          <p className="text-gray-400 text-sm mt-0.5">AI Factory Orchestrator</p>
        </div>
        <RunButton />
      </div>

      {isLoading && <p className="text-gray-400 text-sm">Loading…</p>}
      {error && (
        <p className="text-red-400 text-sm">Error: {(error as Error).message}</p>
      )}

      {/* Live run output */}
      <RunOutput />

      {data && (
        <>
          {/* Last run summary */}
          {data.last_entry && (
            <div>
              <h2 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">
                Last Run
              </h2>
              <pre className="bg-gray-800 border border-gray-700 rounded p-4 text-xs text-gray-200 font-mono whitespace-pre-wrap">
                {data.last_entry}
              </pre>
            </div>
          )}

          {/* Full run report */}
          <ReportViewer
            content={data.report_content}
            title="Full Run Report"
            maxHeight="50vh"
          />

          {/* Session report (collapsible) */}
          {data.session_report && (
            <div>
              <button
                className="text-sm text-gray-400 hover:text-white flex items-center gap-1 transition-colors"
                onClick={() => setShowSession(!showSession)}
              >
                <span className="text-gray-500">{showSession ? '▾' : '▸'}</span>
                Session Report
              </button>
              {showSession && (
                <div className="mt-2">
                  <ReportViewer
                    content={data.session_report}
                    maxHeight="40vh"
                    scrollToBottom={false}
                  />
                </div>
              )}
            </div>
          )}
        </>
      )}
    </div>
  )
}

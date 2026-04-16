import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { fetchQuestions, submitAnswer } from '../api/client'

export default function Questions() {
  const queryClient = useQueryClient()

  const { data, isLoading, error } = useQuery({
    queryKey: ['questions'],
    queryFn: fetchQuestions,
    refetchInterval: 15_000,
  })

  const [answer, setAnswer] = useState('')
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState<string | null>(null)
  const [saveSuccess, setSaveSuccess] = useState(false)
  const [showHistory, setShowHistory] = useState(false)

  const handleSave = async () => {
    if (!answer.trim()) return
    setSaving(true)
    setSaveError(null)
    setSaveSuccess(false)
    try {
      await submitAnswer(answer)
      setAnswer('')
      setSaveSuccess(true)
      queryClient.invalidateQueries({ queryKey: ['questions'] })
      setTimeout(() => setSaveSuccess(false), 4000)
    } catch (e) {
      setSaveError(e instanceof Error ? e.message : 'Failed to save answer')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="p-6 space-y-6 max-w-3xl">
      <h1 className="text-lg font-semibold text-white">Questions</h1>

      {isLoading && <p className="text-gray-400 text-sm">Loading…</p>}
      {error && (
        <p className="text-red-400 text-sm">Error: {(error as Error).message}</p>
      )}

      {data && (
        <>
          {/* Open questions */}
          <div>
            <h2 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">
              Open Questions
            </h2>
            {data.has_questions ? (
              <pre className="bg-gray-800 border border-yellow-700/50 rounded p-4 text-sm text-gray-100 font-mono whitespace-pre-wrap">
                {data.open_questions}
              </pre>
            ) : (
              <div className="bg-gray-800 border border-gray-700 rounded p-4">
                <p className="text-gray-500 text-sm italic">
                  No open questions. The agents will write here if they need clarification.
                </p>
              </div>
            )}
          </div>

          {/* Answer form — only shown when questions are present */}
          {data.has_questions && (
            <div className="space-y-3">
              <h2 className="text-xs font-semibold text-gray-400 uppercase tracking-wider">
                Your Answer
              </h2>
              <textarea
                value={answer}
                onChange={e => setAnswer(e.target.value)}
                placeholder="Type your answer here…"
                rows={6}
                className="w-full bg-gray-800 border border-gray-700 rounded p-3 text-sm text-gray-100 font-mono resize-y focus:outline-none focus:border-blue-500 transition-colors"
              />
              <div className="flex items-center gap-3">
                <button
                  onClick={handleSave}
                  disabled={saving || !answer.trim()}
                  className={`px-4 py-2 rounded text-sm font-medium transition-colors ${
                    saving || !answer.trim()
                      ? 'bg-gray-600 text-gray-400 cursor-not-allowed'
                      : 'bg-blue-600 hover:bg-blue-500 text-white'
                  }`}
                >
                  {saving ? 'Saving…' : 'Save Answer'}
                </button>
                {saveSuccess && (
                  <span className="text-green-400 text-sm">
                    Answer saved. Questions archived.
                  </span>
                )}
                {saveError && (
                  <span className="text-red-400 text-sm">{saveError}</span>
                )}
              </div>
            </div>
          )}

          {/* Answer history (collapsible) */}
          {data.answered_questions && (
            <div>
              <button
                className="text-sm text-gray-400 hover:text-white flex items-center gap-1 transition-colors"
                onClick={() => setShowHistory(!showHistory)}
              >
                <span className="text-gray-500">{showHistory ? '▾' : '▸'}</span>
                Answer History
              </button>
              {showHistory && (
                <pre className="mt-2 bg-gray-950 border border-gray-700 rounded p-4 text-xs text-gray-400 font-mono overflow-auto max-h-80 whitespace-pre-wrap">
                  {data.answered_questions}
                </pre>
              )}
            </div>
          )}
        </>
      )}
    </div>
  )
}

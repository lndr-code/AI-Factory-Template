import { useEffect, useRef } from 'react'

interface Props {
  content: string
  title?: string
  maxHeight?: string
  scrollToBottom?: boolean
}

export default function ReportViewer({
  content,
  title,
  maxHeight = '60vh',
  scrollToBottom = true,
}: Props) {
  const ref = useRef<HTMLPreElement>(null)

  useEffect(() => {
    if (scrollToBottom && ref.current) {
      ref.current.scrollTop = ref.current.scrollHeight
    }
  }, [content, scrollToBottom])

  return (
    <div>
      {title && (
        <h2 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">
          {title}
        </h2>
      )}
      {content ? (
        <pre
          ref={ref}
          className="bg-gray-950 border border-gray-700 rounded p-4 text-xs text-gray-300 font-mono overflow-auto whitespace-pre-wrap"
          style={{ maxHeight }}
        >
          {content}
        </pre>
      ) : (
        <p className="text-gray-500 text-sm italic">No content yet.</p>
      )}
    </div>
  )
}

import type { Task } from '../api/client'

type Status = Task['status']

const styles: Record<Status, string> = {
  open: 'bg-blue-900 text-blue-200 border border-blue-700',
  done: 'bg-green-900 text-green-200 border border-green-700',
  failed: 'bg-red-900 text-red-200 border border-red-700',
  blocked: 'bg-amber-900 text-amber-200 border border-amber-700',
}

export default function StatusBadge({ status }: { status: Status }) {
  return (
    <span className={`inline-block px-2 py-0.5 rounded text-xs font-medium ${styles[status]}`}>
      {status}
    </span>
  )
}

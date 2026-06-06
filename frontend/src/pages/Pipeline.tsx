import KanbanBoard from '../components/KanbanBoard'
import { Download } from 'lucide-react'
import { jobsApi } from '../api/jobs'

export default function Pipeline() {
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-slate-900 dark:text-slate-100">Pipeline</h1>
          <p className="text-sm text-slate-500 dark:text-slate-400">Track jobs through your application process</p>
        </div>
        <button
          onClick={() => jobsApi.exportCsv()}
          className="btn-secondary text-xs"
        >
          <Download size={13} /> Export CSV
        </button>
      </div>
      <KanbanBoard />
    </div>
  )
}

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { ExternalLink, Wand2 } from 'lucide-react'
import clsx from 'clsx'
import type { Job, JobStatus } from '../types'
import { jobsApi } from '../api/jobs'

const COLUMNS: { status: JobStatus; label: string; color: string }[] = [
  { status: 'discovered', label: 'Discovered', color: 'border-t-slate-400' },
  { status: 'saved', label: 'Saved', color: 'border-t-blue-500' },
  { status: 'applied', label: 'Applied', color: 'border-t-violet-500' },
  { status: 'interview', label: 'Interview', color: 'border-t-amber-500' },
  { status: 'offer', label: 'Offer', color: 'border-t-emerald-500' },
  { status: 'rejected', label: 'Rejected', color: 'border-t-red-400' },
]

interface CardProps {
  job: Job
  onMove: (status: JobStatus) => void
}

function KanbanCard({ job, onMove }: CardProps) {
  const nextStatus: Partial<Record<JobStatus, JobStatus>> = {
    discovered: 'saved', saved: 'applied', applied: 'interview', interview: 'offer',
  }
  const next = nextStatus[job.status]

  return (
    <div className="card p-3 text-xs group">
      <div className="font-medium text-slate-800 dark:text-slate-200 line-clamp-2 leading-snug mb-1">
        {job.title}
      </div>
      <div className="text-slate-500 dark:text-slate-400 mb-2">{job.company}</div>
      <div className="flex items-center justify-between">
        <span className="font-mono text-slate-400">{Math.round(job.score * 100)}%</span>
        <div className="flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
          <a href={job.url} target="_blank" rel="noopener" className="p-1 rounded hover:bg-slate-100 dark:hover:bg-slate-700 text-slate-400">
            <ExternalLink size={11} />
          </a>
          {next && (
            <button
              onClick={() => onMove(next)}
              className="px-1.5 py-0.5 rounded bg-blue-600 text-white text-[10px] font-medium"
            >
              → {next}
            </button>
          )}
          {job.status !== 'rejected' && (
            <button
              onClick={() => onMove('rejected')}
              className="px-1.5 py-0.5 rounded bg-red-50 dark:bg-red-900/20 text-red-500 text-[10px] font-medium"
            >
              ✕
            </button>
          )}
        </div>
      </div>
    </div>
  )
}

export default function KanbanBoard() {
  const qc = useQueryClient()
  const { data } = useQuery({
    queryKey: ['jobs', 'all-statuses'],
    queryFn: () => jobsApi.list({ limit: 500 }),
  })

  const moveMutation = useMutation({
    mutationFn: ({ id, status }: { id: number; status: JobStatus }) =>
      jobsApi.updateStatus(id, status),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['jobs'] }),
  })

  const jobs = data?.items ?? []
  const byStatus = (status: JobStatus) => jobs.filter(j => j.status === status)

  return (
    <div className="flex gap-4 overflow-x-auto pb-4">
      {COLUMNS.map(col => {
        const colJobs = byStatus(col.status)
        return (
          <div key={col.status} className="flex-shrink-0 w-56">
            <div className={clsx('card border-t-2 mb-3', col.color)}>
              <div className="px-3 py-2 flex items-center justify-between">
                <span className="text-xs font-semibold text-slate-700 dark:text-slate-300">{col.label}</span>
                <span className="badge bg-slate-100 dark:bg-slate-700 text-slate-500 dark:text-slate-400 text-[10px]">
                  {colJobs.length}
                </span>
              </div>
            </div>
            <div className="space-y-2">
              {colJobs.map(job => (
                <KanbanCard
                  key={job.id}
                  job={job}
                  onMove={(status) => moveMutation.mutate({ id: job.id, status })}
                />
              ))}
              {colJobs.length === 0 && (
                <div className="text-center text-xs text-slate-400 dark:text-slate-600 py-6 border-2 border-dashed border-slate-200 dark:border-slate-700 rounded-lg">
                  Empty
                </div>
              )}
            </div>
          </div>
        )
      })}
    </div>
  )
}

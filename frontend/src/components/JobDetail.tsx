import { useState } from 'react'
import { useQueryClient, useMutation } from '@tanstack/react-query'
import { ExternalLink, Wand2, X, ChevronDown, ChevronUp, StickyNote } from 'lucide-react'
import clsx from 'clsx'
import type { Job, JobStatus } from '../types'
import { parseApiUtc } from '../lib/dateUtils'
import { jobsApi } from '../api/jobs'
import ScoreBreakdown from './ScoreBreakdown'
import TailoringWorkflow from './TailoringWorkflow'
import QuickAnswersPanel from './QuickAnswersPanel'

const STATUSES: { value: JobStatus; label: string }[] = [
  { value: 'discovered', label: 'Discovered' },
  { value: 'saved', label: 'Saved' },
  { value: 'applied', label: 'Applied' },
  { value: 'interview', label: 'Interview' },
  { value: 'offer', label: 'Offer' },
  { value: 'rejected', label: 'Rejected' },
]

interface Props {
  job: Job
  onClose: () => void
}

export default function JobDetail({ job, onClose }: Props) {
  const qc = useQueryClient()
  const [showTailoring, setShowTailoring] = useState(false)
  const [note, setNote] = useState('')
  const [showDesc, setShowDesc] = useState(false)

  const updateMutation = useMutation({
    mutationFn: (data: Partial<Job>) => jobsApi.update(job.id, data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['jobs'] }),
  })

  const noteMutation = useMutation({
    mutationFn: (n: string) => jobsApi.addNote(job.id, n),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['jobs'] })
      setNote('')
    },
  })

  const handleStatusChange = (status: JobStatus) => {
    const extra = status === 'applied' ? { applied_at: new Date().toISOString() } : {}
    updateMutation.mutate({ status, ...extra })
  }

  if (showTailoring) {
    return <TailoringWorkflow job={job} onClose={() => setShowTailoring(false)} />
  }

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-start justify-between gap-3 mb-4">
        <div className="flex-1 min-w-0">
          <h2 className="font-bold text-slate-900 dark:text-slate-100 text-base leading-snug">{job.title}</h2>
          <p className="text-slate-500 dark:text-slate-400 text-sm mt-0.5">{job.company} · {job.location}</p>
        </div>
        <button onClick={onClose} className="p-1 rounded hover:bg-slate-100 dark:hover:bg-slate-700 text-slate-400">
          <X size={16} />
        </button>
      </div>

      {/* Actions */}
      <div className="flex gap-2 mb-4 flex-wrap">
        <a href={job.url} target="_blank" rel="noopener noreferrer" className="btn-secondary text-xs">
          <ExternalLink size={13} /> View Job
        </a>
        <button
          onClick={() => setShowTailoring(true)}
          className="btn-primary text-xs"
        >
          <Wand2 size={13} /> Tailor & Apply
        </button>
      </div>

      {/* Status selector */}
      <div className="mb-4">
        <p className="label">Status</p>
        <div className="flex flex-wrap gap-1">
          {STATUSES.map(s => (
            <button
              key={s.value}
              onClick={() => handleStatusChange(s.value)}
              disabled={updateMutation.isPending}
              className={clsx(
                'px-2.5 py-1 rounded-full text-xs font-medium transition-colors border',
                job.status === s.value
                  ? 'bg-blue-600 border-blue-600 text-white'
                  : 'border-slate-300 dark:border-slate-600 text-slate-600 dark:text-slate-400 hover:border-blue-400'
              )}
            >
              {s.label}
            </button>
          ))}
        </div>
      </div>

      {/* Score */}
      <div className="card p-3 mb-4">
        <ScoreBreakdown scores={job.score_details} total={job.score} />
      </div>

      {/* Description toggle */}
      {job.description && (
        <div className="mb-4">
          <button
            onClick={() => setShowDesc(d => !d)}
            className="flex items-center gap-1 text-xs font-medium text-slate-500 dark:text-slate-400 hover:text-slate-700 dark:hover:text-slate-200"
          >
            {showDesc ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
            Job Description
          </button>
          {showDesc && (
            <div className="mt-2 text-xs text-slate-600 dark:text-slate-300 whitespace-pre-wrap leading-relaxed max-h-48 overflow-y-auto bg-slate-50 dark:bg-slate-900 rounded-lg p-3">
              {job.description}
            </div>
          )}
        </div>
      )}

      {/* Quick Answers — copy-paste application-form fillers */}
      <div className="mb-4">
        <QuickAnswersPanel />
      </div>

      {/* Notes */}
      <div className="mb-4">
        <p className="label flex items-center gap-1"><StickyNote size={11} /> Notes</p>
        {job.notes && (
          <div className="text-xs text-slate-600 dark:text-slate-300 whitespace-pre-wrap bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800 rounded-lg p-2.5 mb-2 leading-relaxed">
            {job.notes}
          </div>
        )}
        <div className="flex gap-2">
          <textarea
            value={note}
            onChange={e => setNote(e.target.value)}
            placeholder="Add a note..."
            rows={2}
            className="input text-xs resize-none flex-1"
          />
          <button
            onClick={() => note.trim() && noteMutation.mutate(note)}
            disabled={!note.trim() || noteMutation.isPending}
            className="btn-primary text-xs self-end"
          >
            Save
          </button>
        </div>
      </div>

      {/* Meta */}
      <div className="text-xs text-slate-400 dark:text-slate-500 space-y-0.5 mt-auto pt-4 border-t border-slate-200 dark:border-slate-700">
        {job.applied_at && <p>Applied: {parseApiUtc(job.applied_at).toLocaleDateString()}</p>}
        <p>Found: {parseApiUtc(job.created_at).toLocaleString()}</p>
      </div>
    </div>
  )
}

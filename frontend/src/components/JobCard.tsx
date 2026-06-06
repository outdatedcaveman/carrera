import { ExternalLink, MapPin, DollarSign, Building2, Sparkles } from 'lucide-react'
import clsx from 'clsx'
import type { Job } from '../types'
import { formatDistanceToNow } from 'date-fns'
import { parseApiUtc } from '../lib/dateUtils'

const CATEGORY_STYLES: Record<string, string> = {
  strong_match: 'bg-emerald-100 dark:bg-emerald-900/30 text-emerald-700 dark:text-emerald-400',
  good_match: 'bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-400',
  worth_a_look: 'bg-amber-100 dark:bg-amber-900/30 text-amber-700 dark:text-amber-400',
  reach: 'bg-slate-100 dark:bg-slate-700 text-slate-600 dark:text-slate-400',
}

const CATEGORY_LABELS: Record<string, string> = {
  strong_match: 'Strong Match',
  good_match: 'Good Match',
  worth_a_look: 'Worth a Look',
  reach: 'Reach',
}

const STATUS_STYLES: Record<string, string> = {
  discovered: 'bg-slate-100 dark:bg-slate-700 text-slate-600 dark:text-slate-300',
  saved: 'bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-400',
  applied: 'bg-violet-100 dark:bg-violet-900/30 text-violet-700 dark:text-violet-400',
  interview: 'bg-amber-100 dark:bg-amber-900/30 text-amber-700 dark:text-amber-400',
  offer: 'bg-emerald-100 dark:bg-emerald-900/30 text-emerald-700 dark:text-emerald-400',
  rejected: 'bg-red-100 dark:bg-red-900/30 text-red-600 dark:text-red-400',
}

interface Props {
  job: Job
  selected?: boolean
  onClick: () => void
}

export default function JobCard({ job, selected, onClick }: Props) {
  const scorePercent = Math.round(job.score * 100)

  const formatSalary = () => {
    if (!job.salary_min && !job.salary_max) return null
    const fmt = (n: number) =>
      job.currency === 'BRL'
        ? `R$${(n / 1000).toFixed(0)}k`
        : `$${(n / 1000).toFixed(0)}k`
    if (job.salary_min && job.salary_max)
      return `${fmt(job.salary_min)} – ${fmt(job.salary_max)}`
    if (job.salary_min) return `${fmt(job.salary_min)}+`
    return null
  }

  const salary = formatSalary()

  return (
    <div
      onClick={onClick}
      className={clsx(
        'card p-4 cursor-pointer transition-all hover:border-blue-300 dark:hover:border-blue-600',
        selected && 'border-blue-400 dark:border-blue-500 ring-1 ring-blue-400 dark:ring-blue-500'
      )}
    >
      <div className="flex items-start justify-between gap-2 mb-2">
        <div className="flex-1 min-w-0">
          <h3 className="font-semibold text-slate-900 dark:text-slate-100 text-sm leading-snug line-clamp-2">
            {job.title}
          </h3>
          <div className="flex items-center gap-1 mt-1 text-slate-500 dark:text-slate-400 text-xs">
            <Building2 size={11} />
            <span className="truncate">{job.company}</span>
          </div>
        </div>

        <div className="shrink-0 flex flex-col items-end gap-1">
          <div className={clsx('badge', CATEGORY_STYLES[job.category])}>
            {job.category === 'strong_match' && <Sparkles size={10} className="mr-0.5" />}
            {CATEGORY_LABELS[job.category]}
          </div>
          <div className="text-xs font-mono font-semibold text-slate-500 dark:text-slate-400">
            {scorePercent}%
          </div>
        </div>
      </div>

      <div className="flex items-center gap-3 text-xs text-slate-500 dark:text-slate-400">
        {job.location && (
          <span className="flex items-center gap-0.5">
            <MapPin size={11} />
            <span className="truncate max-w-[120px]">{job.remote ? 'Remote' : job.location}</span>
          </span>
        )}
        {salary && (
          <span className="flex items-center gap-0.5">
            <DollarSign size={11} />
            {salary}
          </span>
        )}
      </div>

      <div className="flex items-center justify-between mt-3">
        <span className={clsx('badge text-xs', STATUS_STYLES[job.status])}>
          {job.status}
        </span>
        <span className="text-xs text-slate-400 dark:text-slate-500">
          {formatDistanceToNow(parseApiUtc(job.created_at), { addSuffix: true })}
        </span>
      </div>
    </div>
  )
}

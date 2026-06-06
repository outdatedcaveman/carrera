import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Search, Filter, Download, SlidersHorizontal } from 'lucide-react'
import clsx from 'clsx'
import { jobsApi } from '../api/jobs'
import type { Job, JobCategory, JobStatus } from '../types'
import JobCard from '../components/JobCard'
import JobDetail from '../components/JobDetail'
import JobFilters, { EMPTY_FILTERS, type AdvancedFilters } from '../components/JobFilters'

const CATEGORY_FILTERS: { value: JobCategory | ''; label: string }[] = [
  { value: '', label: 'All' },
  { value: 'strong_match', label: 'Strong Match' },
  { value: 'good_match', label: 'Good Match' },
  { value: 'worth_a_look', label: 'Worth a Look' },
  { value: 'reach', label: 'Reach' },
]

const STATUS_FILTERS: { value: string; label: string }[] = [
  { value: '', label: 'All' },
  { value: 'discovered', label: 'New' },
  { value: 'saved', label: 'Saved' },
  { value: 'applied', label: 'Applied' },
  { value: 'interview,offer', label: 'Active' },
  { value: 'rejected', label: 'Rejected' },
]

export default function Jobs() {
  const [search, setSearch] = useState('')
  const [category, setCategory] = useState<string>('')
  const [status, setStatus] = useState<string>('discovered,saved')
  const [sortBy, setSortBy] = useState('score')
  const [selectedJob, setSelectedJob] = useState<Job | null>(null)
  const [page, setPage] = useState(0)
  const [filters, setFilters] = useState<AdvancedFilters>(EMPTY_FILTERS)

  const LIMIT = 40

  const { data, isLoading } = useQuery({
    queryKey: ['jobs', search, category, status, sortBy, page, filters],
    queryFn: () => jobsApi.list({
      search: search || undefined,
      category: category || undefined,
      status: status || undefined,
      source_id: filters.source_id || undefined,
      company: filters.company || undefined,
      location: filters.location || undefined,
      remote: filters.remote || undefined,
      seniority: filters.seniority || undefined,
      salary_min: filters.salary_min ?? undefined,
      salary_max: filters.salary_max ?? undefined,
      posted_within_days: filters.posted_within_days ?? undefined,
      sort_by: sortBy,
      order: 'desc',
      limit: LIMIT,
      offset: page * LIMIT,
    }),
  })

  const jobs = data?.items ?? []
  const total = data?.total ?? 0

  return (
    <div className="flex gap-4 h-[calc(100vh-5.5rem)]">
      {/* Left panel — filters + job list */}
      <div className="flex flex-col w-full lg:w-96 shrink-0">
        {/* Search */}
        <div className="relative mb-3">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
          <input
            type="text"
            placeholder="Search jobs..."
            value={search}
            onChange={e => { setSearch(e.target.value); setPage(0) }}
            className="input pl-9 text-sm"
          />
        </div>

        {/* Status filter */}
        <div className="flex gap-1 overflow-x-auto mb-2 pb-1">
          {STATUS_FILTERS.map(f => (
            <button
              key={f.value}
              onClick={() => { setStatus(f.value); setPage(0) }}
              className={clsx(
                'px-2.5 py-1 rounded-full text-xs font-medium whitespace-nowrap transition-colors border',
                status === f.value
                  ? 'bg-blue-600 border-blue-600 text-white'
                  : 'border-slate-300 dark:border-slate-600 text-slate-600 dark:text-slate-400 hover:border-blue-300'
              )}
            >
              {f.label}
            </button>
          ))}
        </div>

        {/* Advanced filters — collapsible */}
        <JobFilters value={filters} onChange={(next) => { setFilters(next); setPage(0) }} />

        {/* Category + sort bar */}
        <div className="flex items-center gap-2 mb-3">
          <select
            value={category}
            onChange={e => { setCategory(e.target.value); setPage(0) }}
            className="input text-xs py-1 flex-1"
          >
            {CATEGORY_FILTERS.map(f => (
              <option key={f.value} value={f.value}>{f.label}</option>
            ))}
          </select>
          <select
            value={sortBy}
            onChange={e => setSortBy(e.target.value)}
            className="input text-xs py-1 flex-1"
          >
            <option value="score">Sort: Score</option>
            <option value="created_at">Sort: Newest</option>
            <option value="company">Sort: Company</option>
          </select>
          <button
            onClick={() => jobsApi.exportCsv(status || undefined)}
            title="Export CSV"
            className="btn-secondary p-1.5"
          >
            <Download size={13} />
          </button>
        </div>

        {/* Results count */}
        <div className="text-xs text-slate-500 dark:text-slate-400 mb-2">
          {isLoading ? 'Loading...' : `${total} jobs`}
        </div>

        {/* Job list */}
        <div className="flex-1 overflow-y-auto space-y-2 pr-1">
          {isLoading && (
            <div className="space-y-2">
              {[...Array(5)].map((_, i) => (
                <div key={i} className="card p-4 animate-pulse">
                  <div className="h-4 bg-slate-200 dark:bg-slate-700 rounded w-3/4 mb-2" />
                  <div className="h-3 bg-slate-100 dark:bg-slate-800 rounded w-1/2" />
                </div>
              ))}
            </div>
          )}
          {!isLoading && jobs.map(job => (
            <JobCard
              key={job.id}
              job={job}
              selected={selectedJob?.id === job.id}
              onClick={() => setSelectedJob(job)}
            />
          ))}
          {!isLoading && jobs.length === 0 && (
            <div className="text-center text-sm text-slate-400 dark:text-slate-600 py-12 space-y-2">
              <p>No jobs match these filters.</p>
              <p className="text-xs">Try &ldquo;All&rdquo; under status, clear search, or run a fetch from Sources.</p>
              {status !== '' && (
                <button
                  type="button"
                  className="text-blue-500 hover:underline text-xs"
                  onClick={() => { setStatus(''); setPage(0) }}
                >
                  Show all statuses
                </button>
              )}
            </div>
          )}
        </div>

        {/* Pagination */}
        {total > LIMIT && (
          <div className="flex items-center justify-between pt-3 mt-2 border-t border-slate-200 dark:border-slate-700">
            <button
              disabled={page === 0}
              onClick={() => setPage(p => p - 1)}
              className="btn-secondary text-xs disabled:opacity-40"
            >
              Prev
            </button>
            <span className="text-xs text-slate-500 dark:text-slate-400">
              {page * LIMIT + 1}–{Math.min((page + 1) * LIMIT, total)} of {total}
            </span>
            <button
              disabled={(page + 1) * LIMIT >= total}
              onClick={() => setPage(p => p + 1)}
              className="btn-secondary text-xs disabled:opacity-40"
            >
              Next
            </button>
          </div>
        )}
      </div>

      {/* Right panel — job detail */}
      <div className={clsx(
        'flex-1 card p-5 overflow-y-auto hidden lg:block',
        !selectedJob && 'flex items-center justify-center'
      )}>
        {selectedJob ? (
          <JobDetail
            key={selectedJob.id}
            job={selectedJob}
            onClose={() => setSelectedJob(null)}
          />
        ) : (
          <div className="text-center text-slate-400 dark:text-slate-600">
            <SlidersHorizontal size={32} className="mx-auto mb-3 opacity-50" />
            <p className="text-sm">Select a job to see details</p>
          </div>
        )}
      </div>

      {/* Mobile: fullscreen overlay */}
      {selectedJob && (
        <div className="fixed inset-0 bg-white dark:bg-slate-900 z-50 lg:hidden p-4 overflow-y-auto">
          <JobDetail
            key={selectedJob.id}
            job={selectedJob}
            onClose={() => setSelectedJob(null)}
          />
        </div>
      )}
    </div>
  )
}

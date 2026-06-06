import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { RefreshCw, Plus, Trash2, Clock, ToggleLeft, ToggleRight } from 'lucide-react'
import clsx from 'clsx'
import { sourcesApi, type FetchAllResult } from '../api/sources'
import { formatDistanceToNow } from 'date-fns'
import { parseApiUtc } from '../lib/dateUtils'
import type { Source } from '../types'

function invalidateSourcesAndJobs(qc: ReturnType<typeof useQueryClient>) {
  qc.invalidateQueries({ queryKey: ['sources'] })
  qc.invalidateQueries({ queryKey: ['jobs'] })
  qc.invalidateQueries({ queryKey: ['stats'] })
  qc.invalidateQueries({ queryKey: ['jobs-over-time'] })
  qc.invalidateQueries({ queryKey: ['categories'] })
  qc.invalidateQueries({ queryKey: ['companies'] })
}

const SOURCE_TYPES = [
  { value: 'linkedin', label: 'LinkedIn' },
  { value: 'gupy', label: 'Gupy' },
  { value: 'indeed', label: 'Indeed Brasil' },
  { value: 'remoteok', label: 'RemoteOK' },
  { value: 'weworkremotely', label: 'WeWorkRemotely' },
  { value: 'rss', label: 'Generic RSS Feed' },
]

export default function Sources() {
  const qc = useQueryClient()
  const [adding, setAdding] = useState(false)
  const [newName, setNewName] = useState('')
  const [newType, setNewType] = useState('gupy')

  const { data: sources = [] } = useQuery({ queryKey: ['sources'], queryFn: sourcesApi.list })

  const deleteMutation = useMutation({
    mutationFn: sourcesApi.delete,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['sources'] }),
  })

  const toggleMutation = useMutation({
    mutationFn: ({ id, enabled }: { id: number; enabled: boolean }) =>
      sourcesApi.update(id, { enabled }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['sources'] }),
  })

  const fetchMutation = useMutation({
    mutationFn: sourcesApi.triggerFetch,
    onSuccess: () => invalidateSourcesAndJobs(qc),
  })

  const createMutation = useMutation({
    mutationFn: ({ name, type }: { name: string; type: string }) =>
      sourcesApi.create({ name, type, config: {} }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['sources'] })
      setAdding(false)
      setNewName('')
    },
  })

  const fetchAllMutation = useMutation({
    mutationFn: sourcesApi.triggerFetchAll,
    onSuccess: () => invalidateSourcesAndJobs(qc),
  })

  const fetchError =
    fetchMutation.error?.message ?? fetchAllMutation.error?.message ?? null
  const fetchAllResult: FetchAllResult | undefined = fetchAllMutation.data

  return (
    <div className="max-w-3xl space-y-4">
      {fetchError && (
        <div className="card p-3 text-sm text-red-600 dark:text-red-400 bg-red-50 dark:bg-red-950/40 border border-red-200 dark:border-red-900">
          {fetchError}
        </div>
      )}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-slate-900 dark:text-slate-100">Sources</h1>
          <p className="text-sm text-slate-500 dark:text-slate-400">Manage job board scrapers</p>
          <p className="text-xs text-slate-400 dark:text-slate-500 mt-1">
            Fetch runs on the server and can take a few minutes per source. Keep this tab open while &ldquo;Fetch All&rdquo; runs.
          </p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => {
              fetchMutation.reset()
              fetchAllMutation.reset()
              fetchAllMutation.mutate()
            }}
            disabled={fetchAllMutation.isPending}
            className="btn-secondary text-xs"
          >
            <RefreshCw size={13} className={clsx(fetchAllMutation.isPending && 'animate-spin')} />
            Fetch All
          </button>
          <button onClick={() => setAdding(true)} className="btn-primary text-xs">
            <Plus size={13} /> Add Source
          </button>
        </div>
      </div>

      {/* Per-source fetch-all results */}
      {fetchAllResult && (
        <div className="card p-3 space-y-2">
          <div className="flex items-center justify-between">
            <p className="text-xs font-semibold text-slate-700 dark:text-slate-300">
              {fetchAllResult.message}
            </p>
            <button
              onClick={() => fetchAllMutation.reset()}
              className="text-slate-400 hover:text-slate-600 text-xs"
              title="Dismiss"
            >
              ✕
            </button>
          </div>
          <ul className="space-y-1">
            {fetchAllResult.results.map(r => (
              <li
                key={r.id}
                className={clsx(
                  'flex items-start gap-2 text-xs px-2 py-1 rounded',
                  r.ok
                    ? 'text-slate-600 dark:text-slate-400'
                    : 'text-red-600 dark:text-red-400 bg-red-50 dark:bg-red-950/30'
                )}
              >
                <span className="shrink-0 mt-0.5">{r.ok ? '✓' : '✕'}</span>
                <span className="font-medium">{r.name}</span>
                <span className="ml-auto shrink-0 tabular-nums">
                  {r.ok ? `+${r.added} new` : 'failed'}
                </span>
                {!r.ok && r.error && (
                  <span className="basis-full pl-5 text-[11px] opacity-80">{r.error}</span>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Add form */}
      {adding && (
        <div className="card p-4 space-y-3">
          <h3 className="text-sm font-semibold text-slate-700 dark:text-slate-300">New Source</h3>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <p className="label">Name</p>
              <input
                className="input text-sm"
                value={newName}
                onChange={e => setNewName(e.target.value)}
                placeholder="e.g. Gupy - São Paulo"
              />
            </div>
            <div>
              <p className="label">Type</p>
              <select className="input text-sm" value={newType} onChange={e => setNewType(e.target.value)}>
                {SOURCE_TYPES.map(t => (
                  <option key={t.value} value={t.value}>{t.label}</option>
                ))}
              </select>
            </div>
          </div>
          <div className="flex gap-2">
            <button
              onClick={() => createMutation.mutate({ name: newName, type: newType })}
              disabled={!newName.trim() || createMutation.isPending}
              className="btn-primary text-xs"
            >
              Create
            </button>
            <button onClick={() => setAdding(false)} className="btn-secondary text-xs">Cancel</button>
          </div>
        </div>
      )}

      {/* Source list */}
      <div className="space-y-3">
        {sources.map(source => (
          <SourceCard
            key={source.id}
            source={source}
            onToggle={() => toggleMutation.mutate({ id: source.id, enabled: !source.enabled })}
            onFetch={() => fetchMutation.mutate(source.id)}
            onDelete={() => deleteMutation.mutate(source.id)}
            fetching={fetchMutation.variables === source.id && fetchMutation.isPending}
          />
        ))}
        {sources.length === 0 && (
          <div className="card p-8 text-center text-sm text-slate-400 dark:text-slate-600">
            No sources configured yet. Add one above.
          </div>
        )}
      </div>
    </div>
  )
}

function SourceCard({ source, onToggle, onFetch, onDelete, fetching }: {
  source: Source
  onToggle: () => void
  onFetch: () => void
  onDelete: () => void
  fetching: boolean
}) {
  const hasError = !!source.last_error

  return (
    <div className={clsx('card p-4', !source.enabled && 'opacity-60')}>
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="font-medium text-sm text-slate-800 dark:text-slate-200">{source.name}</span>
            <span className="badge bg-slate-100 dark:bg-slate-700 text-slate-500 dark:text-slate-400 text-[10px]">
              {source.type}
            </span>
            {hasError && (
              <span className="badge bg-red-50 dark:bg-red-900/20 text-red-500 text-[10px]">
                error
              </span>
            )}
          </div>

          <div className="flex items-center gap-3 mt-1.5 text-xs text-slate-500 dark:text-slate-400">
            {source.last_fetched ? (
              <span className="flex items-center gap-1">
                <Clock size={11} />
                {formatDistanceToNow(parseApiUtc(source.last_fetched), { addSuffix: true })}
              </span>
            ) : (
              <span className="text-slate-400 dark:text-slate-600">Never fetched</span>
            )}
            <span title="Jobs stored now vs rows ever inserted by this source's scrapes (counter does not go down if you delete jobs)">
              {(source.job_count ?? 0)} jobs
              {(source.jobs_found_total ?? 0) > 0 && (source.job_count ?? 0) !== source.jobs_found_total && (
                <span className="text-slate-400 dark:text-slate-500"> · {source.jobs_found_total} ever ingested</span>
              )}
            </span>
          </div>

          {source.last_error && (
            <p className="text-xs text-red-500 mt-1 truncate">{source.last_error}</p>
          )}
        </div>

        <div className="flex items-center gap-1.5 shrink-0">
          <button
            onClick={onFetch}
            disabled={fetching}
            className="btn-secondary p-1.5"
            title="Fetch now"
          >
            <RefreshCw size={13} className={clsx(fetching && 'animate-spin')} />
          </button>
          <button
            onClick={onToggle}
            className="btn-secondary p-1.5"
            title={source.enabled ? 'Disable' : 'Enable'}
          >
            {source.enabled
              ? <ToggleRight size={13} className="text-blue-500" />
              : <ToggleLeft size={13} />}
          </button>
          <button
            onClick={onDelete}
            className="btn-danger p-1.5"
            title="Delete"
          >
            <Trash2 size={13} />
          </button>
        </div>
      </div>
    </div>
  )
}

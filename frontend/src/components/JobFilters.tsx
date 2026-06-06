/**
 * JobFilters — collapsible advanced-filter panel for the Jobs page.
 *
 * The Jobs page already has primary filters as tabs (status, category, sort).
 * This adds the rest the user asked for: source platform, location, remote
 * format, compensation, posted-within-days, company, seniority. Each
 * dropdown's options are pulled from /api/jobs/filter-options so we only
 * ever show values that exist in the user's actual job set.
 *
 * State is owned by the parent (Jobs.tsx) so filters can persist across
 * pagination / search and the URL stays simple. The "Clear" button resets
 * everything in this panel without touching the parent's status/category
 * tabs.
 */
import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { ChevronDown, ChevronUp, X, SlidersHorizontal } from 'lucide-react'
import clsx from 'clsx'
import { jobsApi } from '../api/jobs'

export interface AdvancedFilters {
  source_id: string                // comma-separated
  company: string                  // comma-separated
  location: string
  remote: 'remote' | 'onsite' | ''
  seniority: string                // comma-separated
  salary_min: number | null
  salary_max: number | null
  posted_within_days: number | null
}

export const EMPTY_FILTERS: AdvancedFilters = {
  source_id: '',
  company: '',
  location: '',
  remote: '',
  seniority: '',
  salary_min: null,
  salary_max: null,
  posted_within_days: null,
}

function activeCount(f: AdvancedFilters): number {
  return Object.values(f).filter(v => v !== '' && v !== null).length
}

function MultiPicker({ label, options, value, onChange, placeholder }: {
  label: string
  options: { value: string; label: string; count: number }[]
  value: string
  onChange: (v: string) => void
  placeholder?: string
}) {
  const selected = new Set(value.split(',').filter(Boolean))
  const toggle = (v: string) => {
    if (selected.has(v)) selected.delete(v)
    else selected.add(v)
    onChange(Array.from(selected).join(','))
  }
  return (
    <div>
      <p className="label flex items-center justify-between">
        {label}
        {selected.size > 0 && (
          <button
            onClick={() => onChange('')}
            className="text-[10px] text-slate-400 hover:text-slate-600 normal-case font-normal"
          >
            clear
          </button>
        )}
      </p>
      {options.length === 0 ? (
        <p className="text-[11px] text-slate-400 dark:text-slate-500 italic">
          {placeholder ?? 'No values yet'}
        </p>
      ) : (
        <div className="flex flex-wrap gap-1">
          {options.map(o => (
            <button
              key={o.value}
              onClick={() => toggle(o.value)}
              className={clsx(
                'text-[11px] px-2 py-0.5 rounded-full border transition-colors',
                selected.has(o.value)
                  ? 'bg-carrera-600 border-carrera-600 text-white'
                  : 'border-slate-300 dark:border-slate-600 text-slate-600 dark:text-slate-300 hover:border-carrera-400'
              )}
              title={`${o.count} jobs`}
            >
              {o.label} <span className="opacity-60">{o.count}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

export default function JobFilters({
  value,
  onChange,
}: {
  value: AdvancedFilters
  onChange: (next: AdvancedFilters) => void
}) {
  const [open, setOpen] = useState(false)
  const { data: opts } = useQuery({
    queryKey: ['job-filter-options'],
    queryFn: jobsApi.filterOptions,
    staleTime: 60_000,
  })

  const set = <K extends keyof AdvancedFilters>(k: K, v: AdvancedFilters[K]) =>
    onChange({ ...value, [k]: v })

  const count = activeCount(value)

  return (
    <div className="card overflow-hidden mb-3">
      <button
        onClick={() => setOpen(o => !o)}
        className="w-full flex items-center justify-between px-3 py-2 hover:bg-slate-50 dark:hover:bg-slate-800/40"
      >
        <span className="flex items-center gap-2 text-xs font-semibold text-slate-700 dark:text-slate-200">
          <SlidersHorizontal size={13} className="text-carrera-600 dark:text-carrera-400" />
          Filters
          {count > 0 && (
            <span className="text-[10px] bg-carrera-100 dark:bg-carrera-900/40 text-carrera-700 dark:text-carrera-300 px-1.5 py-0.5 rounded-full font-medium">
              {count} active
            </span>
          )}
        </span>
        <span className="flex items-center gap-2">
          {count > 0 && (
            <button
              onClick={(e) => { e.stopPropagation(); onChange(EMPTY_FILTERS) }}
              className="text-[11px] text-slate-400 hover:text-red-500 flex items-center gap-1"
              title="Clear all"
            >
              <X size={11} /> clear
            </button>
          )}
          {open ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
        </span>
      </button>

      {open && (
        <div className="p-3 border-t border-slate-200 dark:border-slate-700 space-y-3">
          {/* Source */}
          <MultiPicker
            label="Source platform"
            value={value.source_id}
            onChange={v => set('source_id', v)}
            options={(opts?.sources ?? []).map(s => ({
              value: String(s.id),
              label: s.name,
              count: s.count,
            }))}
            placeholder="No sources yet"
          />

          {/* Seniority */}
          <MultiPicker
            label="Level / seniority"
            value={value.seniority}
            onChange={v => set('seniority', v)}
            options={(opts?.seniority ?? []).map(s => ({
              value: s.value,
              label: s.value,
              count: s.count,
            }))}
            placeholder="Sources didn't tag seniority on these jobs"
          />

          {/* Format */}
          <div>
            <p className="label flex items-center justify-between">
              Work format
              {value.remote && (
                <button onClick={() => set('remote', '')} className="text-[10px] text-slate-400 hover:text-slate-600 normal-case font-normal">clear</button>
              )}
            </p>
            <div className="flex gap-1">
              {[
                { value: 'remote', label: 'Remote' },
                { value: 'onsite', label: 'Hybrid / On-site' },
              ].map(o => (
                <button
                  key={o.value}
                  onClick={() => set('remote', value.remote === o.value ? '' : (o.value as AdvancedFilters['remote']))}
                  className={clsx(
                    'text-[11px] px-2.5 py-1 rounded-full border',
                    value.remote === o.value
                      ? 'bg-carrera-600 border-carrera-600 text-white'
                      : 'border-slate-300 dark:border-slate-600 text-slate-600 dark:text-slate-300 hover:border-carrera-400'
                  )}
                >
                  {o.label}
                </button>
              ))}
            </div>
          </div>

          {/* Location free-text */}
          <div>
            <p className="label">Location contains</p>
            <input
              className="input text-xs"
              value={value.location}
              onChange={e => set('location', e.target.value)}
              placeholder="e.g. São Paulo, EU, Berlin"
            />
          </div>

          {/* Company multi-pick (top 12 by count, with a free-text override) */}
          <MultiPicker
            label="Companies"
            value={value.company}
            onChange={v => set('company', v)}
            options={(opts?.companies ?? []).slice(0, 12).map(c => ({
              value: c.value,
              label: c.value,
              count: c.count,
            }))}
            placeholder="No companies yet"
          />

          {/* Salary */}
          <div>
            <p className="label">Compensation (annual, any currency)</p>
            <div className="grid grid-cols-2 gap-2">
              <input
                type="number"
                className="input text-xs"
                value={value.salary_min ?? ''}
                onChange={e => set('salary_min', e.target.value === '' ? null : Number(e.target.value))}
                placeholder="Min"
              />
              <input
                type="number"
                className="input text-xs"
                value={value.salary_max ?? ''}
                onChange={e => set('salary_max', e.target.value === '' ? null : Number(e.target.value))}
                placeholder="Max"
              />
            </div>
            <p className="text-[10px] text-slate-400 dark:text-slate-500 mt-1">
              Jobs without listed salary are kept (most postings hide it).
            </p>
          </div>

          {/* Posted within */}
          <div>
            <p className="label">Posted within</p>
            <div className="flex gap-1">
              {[
                { value: 1, label: '24h' },
                { value: 3, label: '3d' },
                { value: 7, label: '1w' },
                { value: 14, label: '2w' },
                { value: 30, label: '1mo' },
              ].map(o => (
                <button
                  key={o.value}
                  onClick={() =>
                    set('posted_within_days', value.posted_within_days === o.value ? null : o.value)
                  }
                  className={clsx(
                    'text-[11px] px-2.5 py-1 rounded-full border flex-1',
                    value.posted_within_days === o.value
                      ? 'bg-carrera-600 border-carrera-600 text-white'
                      : 'border-slate-300 dark:border-slate-600 text-slate-600 dark:text-slate-300 hover:border-carrera-400'
                  )}
                >
                  {o.label}
                </button>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

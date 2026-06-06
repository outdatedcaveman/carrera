/**
 * BulkTailor — fan out the tailoring engine across the user's strongest
 * unapplied matches in one click. Lives on the Dashboard so it's the first
 * thing the user sees after their morning fetch.
 *
 * UX shape:
 * 1. Pick how many top matches to tailor (5/10/20).
 * 2. Pick the provider (template = free + instant, anthropic/openai if a key
 *    is set in Settings).
 * 3. Pick language.
 * 4. Click "Tailor N applications". Backend runs them sequentially and
 *    returns a per-job status array. We show a checklist as it streams in,
 *    with one-click links to download each PDF or open the tailored result.
 *
 * The user can then click "Mark as Applied" on any of them once they've
 * actually submitted the application — no autoclicking-Submit (that's a
 * Layer 3 concern in docs/AUTOFILL_ROADMAP.md).
 */
import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  Wand2, Loader2, CheckCircle2, AlertCircle, Send, FileText, ExternalLink,
} from 'lucide-react'
import clsx from 'clsx'
import { Link } from 'react-router-dom'
import { jobsApi } from '../api/jobs'
import { resumesApi } from '../api/resumes'
import { tailoringApi } from '../api/tailoring'
import { appSettingsApi } from '../api/appSettings'

type Provider = 'template' | 'anthropic' | 'openai'

export default function BulkTailor() {
  const qc = useQueryClient()
  const [count, setCount] = useState<5 | 10 | 20>(5)
  const [provider, setProvider] = useState<Provider>('template')
  const [language, setLanguage] = useState<'en' | 'pt'>('en')
  const [results, setResults] = useState<
    | null
    | { message: string; results: Array<{ job_id: number; ok: boolean; application_id: number | null; error: string | null; skipped?: boolean }> }
  >(null)

  // Pull the user's top strong-match unapplied jobs
  const { data: topJobs } = useQuery({
    queryKey: ['top-strong-matches', count],
    queryFn: () => jobsApi.list({
      category: 'strong_match',
      status: 'discovered,saved',
      sort_by: 'score',
      order: 'desc',
      limit: count,
    }),
  })

  const { data: resumes = [] } = useQuery({
    queryKey: ['resumes'],
    queryFn: resumesApi.list,
  })

  const { data: aiSettings } = useQuery({
    queryKey: ['ai-settings'],
    queryFn: appSettingsApi.getAi,
  })

  const defaultResume =
    resumes.find(r => r.is_default && r.language === language) ??
    resumes.find(r => r.language === language) ??
    resumes.find(r => r.is_default) ??
    resumes[0]

  const bulkMutation = useMutation({
    mutationFn: () => tailoringApi.bulk({
      job_ids: (topJobs?.items ?? []).map(j => j.id),
      base_resume_id: defaultResume!.id,
      ai_provider: provider,
      language,
    }),
    onSuccess: (data) => {
      setResults(data)
      qc.invalidateQueries({ queryKey: ['stats'] })
      qc.invalidateQueries({ queryKey: ['recent-activity'] })
      qc.invalidateQueries({ queryKey: ['jobs'] })
    },
  })

  const eligible = topJobs?.items ?? []
  const canRun = !!defaultResume && eligible.length > 0 && !bulkMutation.isPending

  // Don't push the user to LLM providers without a key — disable + tooltip.
  const providerDisabled = (p: Provider) => {
    if (p === 'template') return false
    if (p === 'anthropic') return !aiSettings?.anthropic_api_key_set
    if (p === 'openai') return !aiSettings?.openai_api_key_set
    return false
  }

  return (
    <div className="card p-4 space-y-3">
      <div className="flex items-start gap-2">
        <Wand2 size={16} className="text-carrera-600 dark:text-carrera-400 shrink-0 mt-0.5" />
        <div className="flex-1">
          <h3 className="text-sm font-semibold text-slate-800 dark:text-slate-100">
            Bulk Tailor — your top matches in one click
          </h3>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
            Generate tailored résumés + cover letters for your strongest unapplied jobs. PDFs render in the background; you click "Mark applied" after you submit.
          </p>
        </div>
      </div>

      {!defaultResume ? (
        <p className="text-xs text-amber-600 dark:text-amber-400">
          Set a base CV in <Link to="/resume" className="underline">Resume</Link> first.
        </p>
      ) : eligible.length === 0 ? (
        <p className="text-xs text-slate-500 dark:text-slate-400">
          No unapplied strong matches yet. Run a fetch from <Link to="/sources" className="underline">Sources</Link>.
        </p>
      ) : (
        <>
          <div className="grid grid-cols-3 gap-2 text-xs">
            <div>
              <p className="label">How many</p>
              <div className="flex gap-1">
                {[5, 10, 20].map(n => (
                  <button
                    key={n}
                    onClick={() => setCount(n as 5 | 10 | 20)}
                    className={clsx(
                      'flex-1 py-1 rounded border text-[11px]',
                      count === n
                        ? 'bg-carrera-600 border-carrera-600 text-white'
                        : 'border-slate-300 dark:border-slate-600 text-slate-600 dark:text-slate-300'
                    )}
                  >
                    {n}
                  </button>
                ))}
              </div>
            </div>
            <div>
              <p className="label">Provider</p>
              <select
                className="input text-xs"
                value={provider}
                onChange={e => setProvider(e.target.value as Provider)}
              >
                <option value="template">Template (free)</option>
                <option value="anthropic" disabled={providerDisabled('anthropic')}>
                  Anthropic Claude {providerDisabled('anthropic') && '— set key in Settings'}
                </option>
                <option value="openai" disabled={providerDisabled('openai')}>
                  OpenAI GPT {providerDisabled('openai') && '— set key in Settings'}
                </option>
              </select>
            </div>
            <div>
              <p className="label">Language</p>
              <select
                className="input text-xs"
                value={language}
                onChange={e => setLanguage(e.target.value as 'en' | 'pt')}
              >
                <option value="en">English</option>
                <option value="pt">Português</option>
              </select>
            </div>
          </div>

          {/* Preview of which jobs will get tailored */}
          <details className="text-xs">
            <summary className="cursor-pointer text-slate-500 dark:text-slate-400 hover:text-slate-700 dark:hover:text-slate-200">
              Preview: {eligible.length} job(s) selected
            </summary>
            <ul className="mt-1.5 space-y-0.5 ml-2">
              {eligible.map(j => (
                <li key={j.id} className="text-slate-600 dark:text-slate-400 truncate">
                  <span className="text-slate-400">{Math.round(j.score * 100)}%</span> · {j.title} <span className="text-slate-400">— {j.company}</span>
                </li>
              ))}
            </ul>
          </details>

          <div className="flex items-center gap-2">
            <button
              disabled={!canRun}
              onClick={() => { setResults(null); bulkMutation.mutate() }}
              className="btn-primary text-xs"
            >
              {bulkMutation.isPending ? (
                <><Loader2 size={12} className="animate-spin" /> Tailoring {eligible.length}…</>
              ) : (
                <><Wand2 size={12} /> Tailor {eligible.length} application{eligible.length === 1 ? '' : 's'}</>
              )}
            </button>
            {provider !== 'template' && (
              <span className="text-[10px] text-slate-400">
                ~${(provider === 'anthropic' ? 0.005 : 0.003) * eligible.length}/run estimate
              </span>
            )}
          </div>

          {bulkMutation.error && (
            <p className="text-xs text-red-600 dark:text-red-400 flex items-center gap-1">
              <AlertCircle size={12} /> {(bulkMutation.error as Error).message}
            </p>
          )}

          {results && (
            <div className="border-t border-slate-200 dark:border-slate-700 pt-2 space-y-1">
              <p className="text-xs font-semibold text-slate-700 dark:text-slate-200">{results.message}</p>
              <ul className="space-y-1 text-xs max-h-64 overflow-y-auto">
                {results.results.map(r => {
                  const j = eligible.find(j => j.id === r.job_id)
                  return (
                    <li
                      key={r.job_id}
                      className={clsx(
                        'flex items-start gap-2 px-2 py-1 rounded',
                        r.ok ? 'text-slate-600 dark:text-slate-400' : 'text-red-600 dark:text-red-400 bg-red-50 dark:bg-red-950/30',
                      )}
                    >
                      {r.ok
                        ? <CheckCircle2 size={12} className="text-emerald-500 shrink-0 mt-0.5" />
                        : <AlertCircle size={12} className="shrink-0 mt-0.5" />}
                      <span className="flex-1 truncate">
                        <span className="font-medium">{j?.title ?? `Job #${r.job_id}`}</span>
                        {j?.company && <span className="text-slate-400"> — {j.company}</span>}
                        {r.skipped && <span className="text-[10px] text-slate-400 ml-1.5">(already tailored)</span>}
                      </span>
                      {r.ok && r.application_id && !r.skipped && (
                        <a
                          href={`/api/tailoring/applications/${r.application_id}/resume-pdf`}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-carrera-600 dark:text-carrera-400 hover:underline shrink-0 flex items-center gap-1"
                          title="Download tailored resume PDF"
                        >
                          <FileText size={11} /> PDF
                        </a>
                      )}
                      {j && (
                        <a
                          href={j.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-slate-400 hover:text-carrera-600 shrink-0 flex items-center gap-1"
                          title="Open job posting in browser"
                        >
                          <ExternalLink size={11} />
                        </a>
                      )}
                      {r.ok && r.application_id && (
                        <MarkAppliedButton jobId={r.job_id} />
                      )}
                    </li>
                  )
                })}
              </ul>
            </div>
          )}
        </>
      )}
    </div>
  )
}

function MarkAppliedButton({ jobId }: { jobId: number }) {
  const qc = useQueryClient()
  const [done, setDone] = useState(false)
  const mutation = useMutation({
    mutationFn: () => jobsApi.update(jobId, { status: 'applied', applied_at: new Date().toISOString() }),
    onSuccess: () => {
      setDone(true)
      qc.invalidateQueries({ queryKey: ['stats'] })
      qc.invalidateQueries({ queryKey: ['jobs'] })
      qc.invalidateQueries({ queryKey: ['recent-activity'] })
    },
  })
  if (done) {
    return <span className="text-[10px] text-emerald-600 dark:text-emerald-400 shrink-0 flex items-center gap-1"><CheckCircle2 size={11} /> applied</span>
  }
  return (
    <button
      onClick={() => mutation.mutate()}
      disabled={mutation.isPending}
      className="text-[10px] text-slate-400 hover:text-carrera-600 shrink-0 flex items-center gap-1"
      title="Mark this job as applied (after you've submitted on the company site)"
    >
      <Send size={10} /> mark applied
    </button>
  )
}

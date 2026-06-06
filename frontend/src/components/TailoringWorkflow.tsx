import { useState, useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  X, Wand2, FileText, Download, ChevronRight, ChevronLeft,
  Loader2, AlertCircle, CheckCircle2, Sparkles, DollarSign, Languages, Globe,
  ExternalLink, Copy, Check, Send,
} from 'lucide-react'
import clsx from 'clsx'
import type { Job, TailoringRequest, TailoredApplication } from '../types'
import { tailoringApi } from '../api/tailoring'
import { resumesApi } from '../api/resumes'
import { jobsApi } from '../api/jobs'
import { autofillApi, type AutofillRun } from '../api/autofill'
import ResumePreview from './ResumePreview'

type Step = 'analyze' | 'configure' | 'generate' | 'preview'

const AI_PROVIDERS = [
  { value: 'template', label: 'Template (Free)', desc: 'Rule-based reordering, instant, no AI needed', free: true },
  { value: 'ollama', label: 'Ollama (Free)', desc: 'Local LLM — requires Ollama running locally', free: true },
  { value: 'openai', label: 'OpenAI', desc: 'GPT-4o-mini — highest quality, small cost', free: false },
  { value: 'anthropic', label: 'Anthropic', desc: 'Claude Haiku — fast and affordable', free: false },
]

interface Props {
  job: Job
  onClose: () => void
}

export default function TailoringWorkflow({ job, onClose }: Props) {
  const qc = useQueryClient()
  const [step, setStep] = useState<Step>('analyze')
  const [provider, setProvider] = useState<'template' | 'ollama' | 'openai' | 'anthropic'>('template')
  const [language, setLanguage] = useState<'en' | 'pt'>('en')
  const [customInstructions, setCustomInstructions] = useState('')
  const [selectedEmphasis, setSelectedEmphasis] = useState<string[]>([])
  const [result, setResult] = useState<TailoredApplication | null>(null)
  const [previewTab, setPreviewTab] = useState<'resume' | 'cover_letter'>('resume')

  const { data: resumes } = useQuery({
    queryKey: ['resumes'],
    queryFn: resumesApi.list,
  })

  // Let the user explicitly pick which base CV to tailor from. Default to a
  // resume in the target language if one exists; otherwise fall back to any
  // default; otherwise the first one. We show the choice instead of hiding
  // it so the user notices when they're about to tailor a PT CV into an
  // English application — which used to silently produce a half-translated
  // result.
  const [selectedResumeId, setSelectedResumeId] = useState<number | null>(null)
  const defaultResume =
    (selectedResumeId !== null ? resumes?.find(r => r.id === selectedResumeId) : null)
    ?? resumes?.find(r => r.is_default && r.language === language)
    ?? resumes?.find(r => r.language === language)
    ?? resumes?.find(r => r.is_default)
    ?? resumes?.[0]
  const languageMismatch = !!(defaultResume && defaultResume.language !== language)
  const targetLangResume = resumes?.find(r => r.language === language)

  const translateMutation = useMutation({
    mutationFn: () => resumesApi.translate(defaultResume!.id, { target_language: language }),
    onSuccess: (newResume) => {
      qc.invalidateQueries({ queryKey: ['resumes'] })
      setSelectedResumeId(newResume.id)
    },
  })

  const { data: analysis, isLoading: analyzing, error: analyzeError } = useQuery({
    queryKey: ['analyze', job.id, defaultResume?.id],
    queryFn: () => tailoringApi.analyze(job.id, defaultResume!.id),
    enabled: !!defaultResume,
  })

  const { data: costEst } = useQuery({
    queryKey: ['cost-estimate', job.id, provider, defaultResume?.id],
    queryFn: () => tailoringApi.estimateCost({
      job_id: job.id,
      base_resume_id: defaultResume!.id,
      ai_provider: provider,
      language,
      emphasis: selectedEmphasis,
      custom_instructions: customInstructions,
    }),
    enabled: !!defaultResume && step === 'configure',
  })

  const generateMutation = useMutation({
    mutationFn: (req: TailoringRequest) => tailoringApi.generate(req),
    onSuccess: (data) => {
      setResult(data)
      setStep('preview')
      qc.invalidateQueries({ queryKey: ['jobs'] })
    },
  })

  const handleGenerate = () => {
    if (!defaultResume) return
    setStep('generate')
    generateMutation.mutate({
      job_id: job.id,
      base_resume_id: defaultResume.id,
      ai_provider: provider,
      language,
      emphasis: selectedEmphasis,
      custom_instructions: customInstructions,
    })
  }

  const toggleEmphasis = (skill: string) => {
    setSelectedEmphasis(e =>
      e.includes(skill) ? e.filter(s => s !== skill) : [...e, skill]
    )
  }

  const markApplied = () => {
    jobsApi.update(job.id, { status: 'applied', applied_at: new Date().toISOString() })
      .then(() => {
        qc.invalidateQueries({ queryKey: ['jobs'] })
        onClose()
      })
  }

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between mb-4 pb-3 border-b border-slate-200 dark:border-slate-700">
        <div>
          <h2 className="font-bold text-sm text-slate-900 dark:text-slate-100 flex items-center gap-1.5">
            <Wand2 size={15} className="text-blue-500" />
            Tailor & Apply
          </h2>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">{job.title} at {job.company}</p>
        </div>
        <button onClick={onClose} className="p-1 rounded hover:bg-slate-100 dark:hover:bg-slate-700 text-slate-400">
          <X size={15} />
        </button>
      </div>

      {/* Step: Analyze */}
      {(step === 'analyze' || step === 'configure') && (
        <div className="flex-1 overflow-y-auto space-y-4">
          {analyzing && (
            <div className="flex items-center gap-2 text-sm text-slate-500 dark:text-slate-400">
              <Loader2 size={14} className="animate-spin" />
              Analyzing job requirements...
            </div>
          )}
          {analyzeError && (
            <div className="flex items-center gap-2 text-sm text-red-500">
              <AlertCircle size={14} />
              {String(analyzeError)}
            </div>
          )}

          {analysis && (
            <>
              {/* Match overview */}
              <div className="card p-3">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs font-semibold text-slate-700 dark:text-slate-300">Match Score</span>
                  <span className={clsx(
                    'text-base font-bold',
                    analysis.match_score >= 0.7 ? 'text-emerald-600' :
                    analysis.match_score >= 0.4 ? 'text-blue-600' : 'text-amber-600'
                  )}>
                    {Math.round(analysis.match_score * 100)}%
                  </span>
                </div>
                <div className="w-full bg-slate-200 dark:bg-slate-700 rounded-full h-1.5">
                  <div
                    className="h-1.5 rounded-full bg-blue-500"
                    style={{ width: `${analysis.match_score * 100}%` }}
                  />
                </div>
              </div>

              {/* Side-by-side */}
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <p className="label text-emerald-600 dark:text-emerald-400">Required Skills</p>
                  <div className="flex flex-wrap gap-1">
                    {analysis.required_skills.map(s => (
                      <span key={s} className="badge bg-emerald-50 dark:bg-emerald-900/20 text-emerald-700 dark:text-emerald-400 text-[10px]">{s}</span>
                    ))}
                    {!analysis.required_skills.length && <span className="text-xs text-slate-400">None detected</span>}
                  </div>
                </div>
                <div>
                  <p className="label text-red-500">Skill Gaps</p>
                  <div className="flex flex-wrap gap-1">
                    {analysis.skill_gaps.map(s => (
                      <span key={s} className="badge bg-red-50 dark:bg-red-900/20 text-red-600 dark:text-red-400 text-[10px]">{s}</span>
                    ))}
                    {!analysis.skill_gaps.length && (
                      <span className="badge bg-emerald-50 dark:bg-emerald-900/20 text-emerald-700 dark:text-emerald-400 text-[10px]">
                        <CheckCircle2 size={9} className="mr-0.5" /> No gaps!
                      </span>
                    )}
                  </div>
                </div>
              </div>

              {/* Matching experience */}
              {analysis.matching_experience.length > 0 && (
                <div>
                  <p className="label">Emphasize (click to prioritize)</p>
                  <div className="space-y-1">
                    {analysis.matching_experience.slice(0, 5).map(m => (
                      <button
                        key={m.index}
                        onClick={() => toggleEmphasis(m.company)}
                        className={clsx(
                          'w-full text-left px-2.5 py-2 rounded-lg border text-xs transition-colors',
                          selectedEmphasis.includes(m.company)
                            ? 'border-blue-400 bg-blue-50 dark:bg-blue-900/20 text-blue-700 dark:text-blue-300'
                            : 'border-slate-200 dark:border-slate-700 hover:border-blue-300 text-slate-600 dark:text-slate-300'
                        )}
                      >
                        <span className="font-medium">{m.title}</span>
                        <span className="text-slate-400 dark:text-slate-500"> at {m.company}</span>
                        <span className="ml-2 text-[10px] text-blue-500">({m.matched_skills.length} matches)</span>
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {/* AI provider selection */}
              <div>
                <p className="label">AI Provider</p>
                <div className="space-y-1.5">
                  {AI_PROVIDERS.map(p => (
                    <button
                      key={p.value}
                      onClick={() => setProvider(p.value as typeof provider)}
                      className={clsx(
                        'w-full text-left px-3 py-2 rounded-lg border text-xs transition-colors',
                        provider === p.value
                          ? 'border-blue-400 bg-blue-50 dark:bg-blue-900/20'
                          : 'border-slate-200 dark:border-slate-700 hover:border-slate-300 dark:hover:border-slate-600'
                      )}
                    >
                      <div className="flex items-center justify-between">
                        <span className="font-medium text-slate-800 dark:text-slate-200">{p.label}</span>
                        {p.free && (
                          <span className="badge bg-emerald-100 dark:bg-emerald-900/30 text-emerald-700 dark:text-emerald-400 text-[10px]">Free</span>
                        )}
                        {!p.free && costEst && provider === p.value && (
                          <span className="text-slate-400 text-[10px]">~${costEst.estimated_cost_usd.toFixed(4)}</span>
                        )}
                      </div>
                      <p className="text-slate-500 dark:text-slate-400 mt-0.5">{p.desc}</p>
                    </button>
                  ))}
                </div>
              </div>

              {/* Language */}
              <div>
                <p className="label">Language</p>
                <div className="flex gap-2">
                  {(['en', 'pt'] as const).map(l => (
                    <button
                      key={l}
                      onClick={() => setLanguage(l)}
                      className={clsx(
                        'px-3 py-1.5 rounded-lg border text-xs font-medium transition-colors',
                        language === l
                          ? 'border-blue-400 bg-blue-50 dark:bg-blue-900/20 text-blue-700 dark:text-blue-300'
                          : 'border-slate-200 dark:border-slate-700 text-slate-600 dark:text-slate-400'
                      )}
                    >
                      {l === 'en' ? '🇬🇧 English' : '🇧🇷 Português'}
                      {analysis.language_detected === l && (
                        <span className="ml-1 text-[10px] text-slate-400">(detected)</span>
                      )}
                    </button>
                  ))}
                </div>
              </div>

              {/* Source CV picker — shown so the user knows which CV is being
                  tailored, especially important across language pairs. */}
              {resumes && resumes.length > 0 && (
                <div>
                  <p className="label flex items-center gap-1.5">
                    <FileText size={11} /> Source CV
                  </p>
                  <select
                    className="input text-xs"
                    value={defaultResume?.id ?? ''}
                    onChange={e => setSelectedResumeId(Number(e.target.value))}
                  >
                    {resumes.map(r => (
                      <option key={r.id} value={r.id}>
                        {r.name} — {r.language.toUpperCase()}{r.is_default ? ' (default)' : ''}
                      </option>
                    ))}
                  </select>
                </div>
              )}

              {/* Language mismatch warning — the most common failure mode is
                  picking a target language that doesn't match the source CV.
                  The template engine only translates the summary, so bullets
                  end up half in PT, half in EN. Surface clearly. */}
              {languageMismatch && (
                <div className="card p-3 bg-amber-50/70 dark:bg-amber-900/20 border-amber-200 dark:border-amber-900">
                  <div className="flex items-start gap-2">
                    <AlertCircle size={14} className="text-amber-600 dark:text-amber-400 shrink-0 mt-0.5" />
                    <div className="flex-1 text-xs text-slate-700 dark:text-slate-300 space-y-1.5">
                      <p className="font-semibold">
                        Language mismatch: source CV is{' '}
                        <span className="text-amber-700 dark:text-amber-300">{defaultResume!.language.toUpperCase()}</span>,
                        target is{' '}
                        <span className="text-amber-700 dark:text-amber-300">{language.toUpperCase()}</span>.
                      </p>
                      <p className="text-slate-500 dark:text-slate-400">
                        Bullets will stay in {defaultResume!.language.toUpperCase()} unless you translate first.
                        {targetLangResume && targetLangResume.id !== defaultResume!.id && (
                          <> A {language.toUpperCase()} CV exists — switch above.</>
                        )}
                      </p>
                      {!targetLangResume && (
                        <button
                          onClick={() => translateMutation.mutate()}
                          disabled={translateMutation.isPending}
                          className="btn-primary text-xs"
                        >
                          {translateMutation.isPending ? (
                            <><Loader2 size={11} className="animate-spin" /> Translating…</>
                          ) : (
                            <><Languages size={11} /> Translate {defaultResume!.language.toUpperCase()} → {language.toUpperCase()} now</>
                          )}
                        </button>
                      )}
                      {translateMutation.error && (
                        <p className="text-red-600 dark:text-red-400 text-[11px]">
                          {(translateMutation.error as Error).message}
                        </p>
                      )}
                    </div>
                  </div>
                </div>
              )}

              {/* Custom instructions */}
              <div>
                <p className="label">Custom instructions (optional)</p>
                <textarea
                  value={customInstructions}
                  onChange={e => setCustomInstructions(e.target.value)}
                  placeholder="e.g. Emphasize my experience with institutional investors..."
                  rows={2}
                  className="input text-xs resize-none"
                />
              </div>
            </>
          )}
        </div>
      )}

      {/* Step: Generating */}
      {step === 'generate' && (
        <div className="flex-1 flex items-center justify-center">
          <div className="text-center space-y-3">
            <Loader2 size={32} className="animate-spin mx-auto text-blue-500" />
            <p className="text-sm font-medium text-slate-700 dark:text-slate-300">
              {provider === 'template' ? 'Tailoring resume...' : `Running ${provider} model...`}
            </p>
            <p className="text-xs text-slate-400">Generating resume + cover letter</p>
          </div>
        </div>
      )}

      {/* Step: Preview */}
      {step === 'preview' && result && (
        <div className="flex-1 overflow-y-auto space-y-4">
          <div className="flex items-center gap-2 text-xs font-medium">
            <span className="badge bg-emerald-100 dark:bg-emerald-900/30 text-emerald-700 dark:text-emerald-400">
              <CheckCircle2 size={10} className="mr-0.5" /> Generated with {result.ai_model_used}
            </span>
            {result.ai_cost_usd > 0 && (
              <span className="text-slate-400">Cost: ${result.ai_cost_usd.toFixed(4)}</span>
            )}
          </div>

          {/* Submit-on-company-site checklist. Carrera does NOT submit
              applications for the user — every ATS form is different and
              auto-submission is on the autofill roadmap (Layer 3, Playwright
              driver). For now the right thing is to make the manual flow as
              friction-free as possible: open the posting, give them PDFs +
              copy-able cover letter, then Mark Applied when they're done. */}
          <ApplyChecklist job={job} result={result} onMarkApplied={markApplied} />

          {/* Tab switcher */}
          <div className="flex gap-1 bg-slate-100 dark:bg-slate-800 rounded-lg p-1">
            {(['resume', 'cover_letter'] as const).map(tab => (
              <button
                key={tab}
                onClick={() => setPreviewTab(tab)}
                className={clsx(
                  'flex-1 py-1.5 text-xs font-medium rounded-md transition-colors',
                  previewTab === tab
                    ? 'bg-white dark:bg-slate-700 text-slate-900 dark:text-slate-100 shadow-sm'
                    : 'text-slate-500 dark:text-slate-400 hover:text-slate-700 dark:hover:text-slate-200'
                )}
              >
                {tab === 'resume' ? 'Resume' : 'Cover Letter'}
              </button>
            ))}
          </div>

          {previewTab === 'resume' && (
            <ResumePreview cv={result.tailored_resume_data} />
          )}
          {previewTab === 'cover_letter' && (
            <div className="bg-white dark:bg-slate-800 rounded-lg border border-slate-200 dark:border-slate-700 p-4 relative">
              <CopyButton text={result.cover_letter_text} className="absolute top-2 right-2" />
              <pre className="text-xs text-slate-700 dark:text-slate-300 whitespace-pre-wrap font-sans leading-relaxed">
                {result.cover_letter_text}
              </pre>
            </div>
          )}
        </div>
      )}

      {/* Footer actions */}
      {(step === 'analyze' || step === 'configure') && analysis && (
        <div className="mt-4 pt-3 border-t border-slate-200 dark:border-slate-700 flex justify-between">
          <button onClick={onClose} className="btn-secondary text-xs">
            Cancel
          </button>
          <button onClick={handleGenerate} className="btn-primary text-xs">
            <Sparkles size={13} />
            Generate Tailored Application
            <ChevronRight size={13} />
          </button>
        </div>
      )}

      {step === 'preview' && (
        <div className="mt-4 pt-3 border-t border-slate-200 dark:border-slate-700 flex justify-between">
          <button onClick={() => setStep('analyze')} className="btn-secondary text-xs">
            <ChevronLeft size={13} /> Regenerate
          </button>
          <button onClick={onClose} className="btn-secondary text-xs">
            Done
          </button>
        </div>
      )}
    </div>
  )
}

/* ApplyChecklist — the primary action panel after generation.
 *
 * Three layered affordances, in priority order:
 *
 *   1. **Carrera autofill** (Layer 3): launches system Chrome via
 *      Playwright, navigates to the posting, and types the user's Quick
 *      Answers + tailored CV into matching form fields. User reviews and
 *      clicks Submit themselves — Carrera never submits.
 *   2. **Open application** in the default browser, for ATSes the
 *      heuristic doesn't handle yet (or when the user prefers their own
 *      session/cookies/extensions).
 *   3. **Manual fallback** — download PDFs, copy cover letter, mark
 *      applied after submitting.
 *
 * The autofill is opt-in and shows clear progress + a per-field report
 * after it finishes, so the user can verify what was filled vs. what they
 * still need to do by hand.
 */
function ApplyChecklist({ job, result, onMarkApplied }: {
  job: { url: string; company: string; title: string }
  result: { id: number; resume_pdf_path: string | null; cover_letter_pdf_path: string | null; cover_letter_text: string }
  onMarkApplied: () => void
}) {
  const [autofillState, setAutofillState] = useState<AutofillRun | null>(null)
  const [autofillError, setAutofillError] = useState<string | null>(null)

  const startAutofill = async () => {
    setAutofillError(null)
    try {
      const run = await autofillApi.start(result.id)
      setAutofillState(run)
    } catch (e) {
      setAutofillError((e as Error).message)
    }
  }

  // Poll status while the run is active. Stop once it lands in a terminal
  // state to avoid spinning the API forever.
  useEffect(() => {
    if (!autofillState) return
    const terminal = ['done', 'error', 'user_closed']
    if (terminal.includes(autofillState.status)) return
    const t = setInterval(async () => {
      try {
        const next = await autofillApi.status(result.id)
        setAutofillState(next)
      } catch {
        // ignore — we'll catch up on the next tick
      }
    }, 1000)
    return () => clearInterval(t)
  }, [autofillState?.status, result.id])

  const stopAutofill = async () => {
    try { await autofillApi.stop(result.id) } catch {}
    if (autofillState) setAutofillState({ ...autofillState, status: 'user_closed' })
  }

  const isRunning = autofillState && !['done', 'error', 'user_closed'].includes(autofillState.status)
  const isDone = autofillState?.status === 'done'

  return (
    <div className="card p-3 space-y-2.5 bg-gradient-to-br from-carrera-50/60 to-white dark:from-carrera-900/20 dark:to-slate-800 border-carrera-100 dark:border-carrera-900">
      <div className="flex items-start gap-2">
        <Send size={14} className="text-carrera-600 dark:text-carrera-400 shrink-0 mt-0.5" />
        <div className="flex-1">
          <p className="text-xs font-semibold text-slate-800 dark:text-slate-200">
            Submit on {job.company}'s site
          </p>
          <p className="text-[11px] text-slate-500 dark:text-slate-400 mt-0.5">
            Carrera fills the boring fields for you (name, email, work auth, salary…) but never clicks Submit. You review and finish.
          </p>
        </div>
      </div>

      {/* Primary action: Carrera autofill via Playwright */}
      {!autofillState && (
        <button
          onClick={startAutofill}
          className="btn-primary text-xs w-full justify-center"
        >
          <Sparkles size={12} /> Carrera autofill — open & fill on {job.company}'s site
        </button>
      )}

      {autofillState && (
        <AutofillStatus
          run={autofillState}
          isRunning={!!isRunning}
          isDone={!!isDone}
          onStop={stopAutofill}
        />
      )}

      {autofillError && (
        <div className="text-[11px] text-red-600 dark:text-red-400 bg-red-50 dark:bg-red-950/30 rounded p-2">
          {autofillError}
          {autofillError.includes('Playwright') && (
            <p className="text-[10px] text-slate-500 dark:text-slate-500 mt-1">
              One-time setup. After installing, restart Carrera.
            </p>
          )}
        </div>
      )}

      {/* Secondary: open in user's own browser */}
      <a
        href={job.url}
        target="_blank"
        rel="noopener noreferrer"
        className="btn-secondary text-xs w-full justify-center"
      >
        <ExternalLink size={12} /> Or open in my browser ({job.company})
      </a>

      {/* Manual fallback: download PDFs, copy cover letter */}
      <div className="grid grid-cols-2 gap-2">
        {result.resume_pdf_path ? (
          <a
            href={tailoringApi.resumePdfUrl(result.id)}
            target="_blank"
            rel="noopener noreferrer"
            className="btn-secondary text-xs justify-center"
          >
            <Download size={12} /> Resume PDF
          </a>
        ) : (
          <button disabled className="btn-secondary text-xs justify-center opacity-50 cursor-not-allowed">
            <AlertCircle size={12} /> Resume PDF unavailable
          </button>
        )}
        {result.cover_letter_pdf_path ? (
          <a
            href={tailoringApi.coverLetterPdfUrl(result.id)}
            target="_blank"
            rel="noopener noreferrer"
            className="btn-secondary text-xs justify-center"
          >
            <Download size={12} /> Cover Letter PDF
          </a>
        ) : (
          <button disabled className="btn-secondary text-xs justify-center opacity-50 cursor-not-allowed">
            <AlertCircle size={12} /> Cover Letter PDF unavailable
          </button>
        )}
        <CopyButton
          text={result.cover_letter_text}
          label="Copy cover letter"
          className="btn-secondary text-xs justify-center"
        />
        <button onClick={onMarkApplied} className="btn-primary text-xs justify-center">
          <CheckCircle2 size={12} /> Mark as applied
        </button>
      </div>
    </div>
  )
}

function AutofillStatus({ run, isRunning, isDone, onStop }: {
  run: AutofillRun
  isRunning: boolean
  isDone: boolean
  onStop: () => void
}) {
  const [showReport, setShowReport] = useState(false)

  const filledCount = run.reports.filter(r => r.status === 'filled').length
  const skippedNoData = run.reports.filter(r => r.status === 'skipped_no_data').length
  const skippedUnknown = run.reports.filter(r => r.status === 'skipped_unknown').length
  const errored = run.reports.filter(r => r.status === 'error').length

  return (
    <div className="rounded-lg border border-carrera-200 dark:border-carrera-800 bg-white dark:bg-slate-900 p-2.5 space-y-1.5">
      <div className="flex items-center gap-2">
        {isRunning && <Loader2 size={12} className="animate-spin text-carrera-600 dark:text-carrera-400" />}
        {isDone && <CheckCircle2 size={12} className="text-emerald-500" />}
        {run.status === 'error' && <AlertCircle size={12} className="text-red-500" />}
        {run.status === 'user_closed' && <X size={12} className="text-slate-400" />}
        <span className="text-[11px] font-medium text-slate-700 dark:text-slate-300 flex-1 truncate">
          {run.message || run.status}
        </span>
        <span className="text-[10px] text-slate-400">{run.elapsed_s}s</span>
      </div>

      {(isDone || run.status === 'user_closed') && run.fields_total > 0 && (
        <div className="flex items-center gap-2 text-[10px]">
          <span className="badge bg-emerald-50 dark:bg-emerald-900/20 text-emerald-700 dark:text-emerald-400">
            {filledCount} filled
          </span>
          {skippedNoData > 0 && (
            <span className="badge bg-amber-50 dark:bg-amber-900/20 text-amber-700 dark:text-amber-400">
              {skippedNoData} need data
            </span>
          )}
          {skippedUnknown > 0 && (
            <span className="badge bg-slate-100 dark:bg-slate-800 text-slate-500">
              {skippedUnknown} unknown
            </span>
          )}
          {errored > 0 && (
            <span className="badge bg-red-50 dark:bg-red-900/20 text-red-600 dark:text-red-400">
              {errored} errored
            </span>
          )}
          <button
            onClick={() => setShowReport(s => !s)}
            className="ml-auto text-[10px] text-slate-500 hover:text-carrera-600"
          >
            {showReport ? 'hide' : 'details'}
          </button>
        </div>
      )}

      {showReport && run.reports.length > 0 && (
        <ul className="text-[10px] space-y-0.5 max-h-48 overflow-y-auto pr-1 border-t border-slate-200 dark:border-slate-700 pt-1.5">
          {run.reports.map((r, i) => (
            <li key={i} className="flex items-start gap-1.5">
              <span className="shrink-0 mt-0.5">
                {r.status === 'filled' ? '✓' : r.status === 'error' ? '✕' : '○'}
              </span>
              <span className="flex-1 truncate text-slate-600 dark:text-slate-400">
                <span className="font-medium">{r.field_type ?? '?'}</span>
                <span className="text-slate-400"> — {r.label}</span>
                {r.value_filled && <span className="text-slate-500"> → {r.value_filled.slice(0, 40)}</span>}
                {r.error && <span className="text-red-500"> ({r.error})</span>}
              </span>
            </li>
          ))}
        </ul>
      )}

      {isRunning && (
        <button onClick={onStop} className="text-[10px] text-slate-400 hover:text-red-500">
          Stop & close browser
        </button>
      )}
    </div>
  )
}

function CopyButton({ text, label, className }: {
  text: string
  label?: string
  className?: string
}) {
  const [copied, setCopied] = useState(false)
  const handle = async () => {
    try {
      await navigator.clipboard.writeText(text)
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    } catch {
      // ignore — some webview contexts deny clipboard
    }
  }
  return (
    <button
      onClick={handle}
      className={className ?? 'p-1.5 rounded hover:bg-slate-100 dark:hover:bg-slate-700 text-slate-500'}
      title="Copy to clipboard"
    >
      {copied ? <Check size={12} className="text-emerald-500" /> : <Copy size={12} />}
      {label && (copied ? ' Copied!' : ' ' + label)}
    </button>
  )
}

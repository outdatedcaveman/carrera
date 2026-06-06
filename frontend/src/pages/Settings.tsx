import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  Plus, Trash2, Save, ChevronDown, ChevronUp, KeyRound, CheckCircle2,
  ClipboardList, RefreshCw,
} from 'lucide-react'
import { profilesApi } from '../api/profiles'
import { appSettingsApi, type AISettingsUpdate } from '../api/appSettings'
import { quickAnswersApi, type QuickAnswersData, type QuickAnswersPatch } from '../api/quickAnswers'
import type { SearchProfile, SearchProfileConfig } from '../types'
import clsx from 'clsx'

const DEFAULT_CONFIG: SearchProfileConfig = {
  titles: [],
  locations: [],
  salary_min_brl: null,
  salary_max_brl: null,
  salary_min_usd: null,
  salary_max_usd: null,
  remote_preference: 'any',
  required_keywords: [],
  preferred_keywords: [],
  excluded_keywords: [],
  excluded_companies: [],
  scoring_weights: { title: 0.35, location: 0.20, salary: 0.15, skills: 0.20, seniority: 0.10 },
}

function TagInput({ value, onChange, placeholder }: {
  value: string[]
  onChange: (v: string[]) => void
  placeholder?: string
}) {
  const [input, setInput] = useState('')

  const add = () => {
    const v = input.trim()
    if (v && !value.includes(v)) onChange([...value, v])
    setInput('')
  }

  return (
    <div>
      <div className="flex flex-wrap gap-1 mb-1.5">
        {value.map(t => (
          <span key={t} className="badge bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 cursor-pointer" onClick={() => onChange(value.filter(v => v !== t))}>
            {t} ×
          </span>
        ))}
      </div>
      <div className="flex gap-1">
        <input
          className="input text-xs flex-1"
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && (e.preventDefault(), add())}
          placeholder={placeholder}
        />
        <button onClick={add} className="btn-secondary text-xs">Add</button>
      </div>
    </div>
  )
}

function ProfileEditor({ profile }: { profile: SearchProfile }) {
  const qc = useQueryClient()
  const [config, setConfig] = useState<SearchProfileConfig>(profile.config as SearchProfileConfig)
  const [expanded, setExpanded] = useState(false)
  const [dirty, setDirty] = useState(false)

  const updateConfig = (patch: Partial<SearchProfileConfig>) => {
    setConfig(c => ({ ...c, ...patch }))
    setDirty(true)
  }

  const saveMutation = useMutation({
    mutationFn: () => profilesApi.update(profile.id, { config }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['profiles'] })
      setDirty(false)
    },
  })

  const deleteMutation = useMutation({
    mutationFn: () => profilesApi.delete(profile.id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['profiles'] }),
  })

  const toggleMutation = useMutation({
    mutationFn: () => profilesApi.update(profile.id, { enabled: !profile.enabled }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['profiles'] }),
  })

  return (
    <div className="card overflow-hidden">
      <div
        className="flex items-center justify-between p-4 cursor-pointer hover:bg-slate-50 dark:hover:bg-slate-700/50"
        onClick={() => setExpanded(e => !e)}
      >
        <div className="flex items-center gap-2">
          <span className="font-medium text-sm text-slate-800 dark:text-slate-200">{profile.name}</span>
          <span className={clsx('badge text-[10px]', profile.enabled ? 'bg-emerald-100 dark:bg-emerald-900/30 text-emerald-700 dark:text-emerald-400' : 'bg-slate-100 dark:bg-slate-700 text-slate-500')}>
            {profile.enabled ? 'Active' : 'Disabled'}
          </span>
        </div>
        <div className="flex items-center gap-1.5" onClick={e => e.stopPropagation()}>
          {dirty && (
            <button onClick={() => saveMutation.mutate()} disabled={saveMutation.isPending} className="btn-primary text-xs">
              <Save size={12} /> Save
            </button>
          )}
          <button onClick={() => toggleMutation.mutate()} className="btn-secondary text-xs">
            {profile.enabled ? 'Disable' : 'Enable'}
          </button>
          <button onClick={() => deleteMutation.mutate()} className="btn-danger p-1.5">
            <Trash2 size={13} />
          </button>
          {expanded ? <ChevronUp size={15} className="text-slate-400" /> : <ChevronDown size={15} className="text-slate-400" />}
        </div>
      </div>

      {expanded && (
        <div className="p-4 pt-0 border-t border-slate-200 dark:border-slate-700 space-y-4">
          <div>
            <p className="label">Target Titles</p>
            <TagInput
              value={config.titles}
              onChange={v => updateConfig({ titles: v })}
              placeholder="e.g. Program Manager"
            />
          </div>
          <div>
            <p className="label">Target Locations</p>
            <TagInput
              value={config.locations}
              onChange={v => updateConfig({ locations: v })}
              placeholder="e.g. São Paulo"
            />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <p className="label">Min Salary (BRL)</p>
              <input
                type="number"
                className="input text-sm"
                value={config.salary_min_brl ?? ''}
                onChange={e => updateConfig({ salary_min_brl: e.target.value ? Number(e.target.value) : null })}
                placeholder="e.g. 8000"
              />
            </div>
            <div>
              <p className="label">Remote Preference</p>
              <select
                className="input text-sm"
                value={config.remote_preference}
                onChange={e => updateConfig({ remote_preference: e.target.value as SearchProfileConfig['remote_preference'] })}
              >
                <option value="any">Any</option>
                <option value="remote">Remote Only</option>
                <option value="hybrid">Hybrid OK</option>
                <option value="onsite">On-site Only</option>
              </select>
            </div>
          </div>
          <div>
            <p className="label">Preferred Keywords</p>
            <TagInput
              value={config.preferred_keywords}
              onChange={v => updateConfig({ preferred_keywords: v })}
              placeholder="e.g. inovação"
            />
          </div>
          <div>
            <p className="label">Excluded Keywords</p>
            <TagInput
              value={config.excluded_keywords}
              onChange={v => updateConfig({ excluded_keywords: v })}
              placeholder="e.g. estágio"
            />
          </div>
          <div>
            <p className="label">Excluded Companies</p>
            <TagInput
              value={config.excluded_companies}
              onChange={v => updateConfig({ excluded_companies: v })}
              placeholder="e.g. Company Name"
            />
          </div>

          {/* Scoring weights */}
          <div>
            <p className="label">Scoring Weights</p>
            <div className="space-y-2">
              {Object.entries(config.scoring_weights).map(([dim, weight]) => (
                <div key={dim} className="flex items-center gap-3">
                  <span className="text-xs text-slate-600 dark:text-slate-400 w-20 capitalize">{dim}</span>
                  <input
                    type="range"
                    min="0"
                    max="1"
                    step="0.05"
                    value={weight}
                    onChange={e => updateConfig({
                      scoring_weights: { ...config.scoring_weights, [dim]: Number(e.target.value) }
                    })}
                    className="flex-1"
                  />
                  <span className="text-xs font-mono text-slate-500 dark:text-slate-400 w-8 text-right">
                    {Math.round(weight * 100)}%
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

/**
 * Single API-key input. Always visible (no "edit"-toggle that hides the
 * field on first load — that's what led to a user pasting their key into
 * the model field). When a key is already set, shows a masked hint + a
 * "Replace" toggle that opens a fresh empty input. Pasting a key-shaped
 * value will visibly fill the input without ever auto-saving — the user
 * still has to click the section's Save button.
 */
function ApiKeyField({
  label, subLabel, isSet, hint, draftValue, onChange, placeholder,
}: {
  label: string
  subLabel?: string
  isSet: boolean
  hint: string
  draftValue: string | undefined
  onChange: (value: string) => void
  placeholder: string
}) {
  const [replacing, setReplacing] = useState(false)
  const showInput = !isSet || replacing || draftValue !== undefined

  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between">
        <p className="label flex items-center gap-1.5">
          {label}
          {isSet && !replacing && draftValue === undefined && (
            <span className="text-emerald-600 dark:text-emerald-400 flex items-center gap-1 text-[10px] normal-case font-normal">
              <CheckCircle2 size={11} /> set ({hint})
            </span>
          )}
          {subLabel && (
            <span className="text-[10px] text-slate-400 normal-case font-normal">{subLabel}</span>
          )}
        </p>
        {isSet && !replacing && draftValue === undefined && (
          <button
            onClick={() => { setReplacing(true); onChange('') }}
            className="text-[11px] text-slate-400 hover:text-carrera-600"
          >
            replace
          </button>
        )}
      </div>
      {showInput && (
        <input
          type="password"
          autoComplete="off"
          autoFocus={replacing}
          className="input text-xs font-mono"
          value={draftValue ?? ''}
          onChange={e => onChange(e.target.value)}
          placeholder={placeholder}
        />
      )}
    </div>
  )
}


function AIProviderSection() {
  const qc = useQueryClient()
  const { data: ai } = useQuery({ queryKey: ['ai-settings'], queryFn: appSettingsApi.getAi })
  const [draft, setDraft] = useState<AISettingsUpdate>({})
  // We always show the API-key inputs; "edit" lives on each provider so the
  // user clears the masked placeholder before pasting a new value. Stacking
  // the API-key field behind a toggle while leaving the model field always
  // visible (the previous design) led to users pasting their key into the
  // model input. See https://github.com/.../issues — bug fix Apr 2026.
  const [showAdvanced, setShowAdvanced] = useState(false)

  const saveMutation = useMutation({
    mutationFn: (patch: AISettingsUpdate) => appSettingsApi.updateAi(patch),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['ai-settings'] })
      setDraft({})
    },
  })

  const dirty = Object.keys(draft).length > 0

  if (!ai) return null

  return (
    <section>
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-sm font-semibold text-slate-700 dark:text-slate-300 flex items-center gap-2">
          <KeyRound size={14} className="text-carrera-600 dark:text-carrera-400" />
          AI Provider
        </h2>
        {dirty && (
          <button
            onClick={() => saveMutation.mutate(draft)}
            disabled={saveMutation.isPending}
            className="btn-primary text-xs"
          >
            <Save size={12} /> Save
          </button>
        )}
      </div>

      <div className="card p-4 space-y-4">
        <p className="text-xs text-slate-500 dark:text-slate-400">
          Carrera uses an LLM to parse your CV PDF, tailor resumes to specific jobs, and draft cover letters.
          Set at least one API key — Anthropic is recommended for quality on Haiku 4.5 (~$0.001 per CV import, ~$0.005 per tailoring).
        </p>

        <ApiKeyField
          label="Anthropic API Key"
          isSet={ai.anthropic_api_key_set}
          hint={ai.anthropic_api_key_hint}
          draftValue={draft.anthropic_api_key}
          onChange={(v) => setDraft(d => ({ ...d, anthropic_api_key: v }))}
          placeholder="sk-ant-api03-…"
        />
        <ApiKeyField
          label="OpenAI API Key"
          subLabel="(fallback)"
          isSet={ai.openai_api_key_set}
          hint={ai.openai_api_key_hint}
          draftValue={draft.openai_api_key}
          onChange={(v) => setDraft(d => ({ ...d, openai_api_key: v }))}
          placeholder="sk-…"
        />

        <div className="border-t border-slate-200 dark:border-slate-700 pt-3">
          <button
            onClick={() => setShowAdvanced(s => !s)}
            className="text-[11px] text-slate-500 hover:text-carrera-600 flex items-center gap-1"
          >
            {showAdvanced ? <ChevronUp size={11} /> : <ChevronDown size={11} />}
            Advanced — model overrides
          </button>
          {showAdvanced && (
            <div className="grid grid-cols-2 gap-3 mt-3">
              <div>
                <p className="label text-slate-400">Anthropic model</p>
                <input
                  className="input text-xs font-mono"
                  value={draft.anthropic_model ?? ai.anthropic_model}
                  onChange={e => setDraft(d => ({ ...d, anthropic_model: e.target.value }))}
                  placeholder="claude-haiku-4-5-20251001"
                />
              </div>
              <div>
                <p className="label text-slate-400">OpenAI model</p>
                <input
                  className="input text-xs font-mono"
                  value={draft.openai_model ?? ai.openai_model}
                  onChange={e => setDraft(d => ({ ...d, openai_model: e.target.value }))}
                  placeholder="gpt-4o-mini"
                />
              </div>
            </div>
          )}
        </div>

        <p className="text-[11px] text-slate-400 dark:text-slate-500">
          Keys are stored locally in <code>~/.carrera/careerops.db</code> and sent only to the provider you select. Carrera never uploads them anywhere.
        </p>
      </div>
    </section>
  )
}

/* ── Quick Answers ─────────────────────────────────────────────────────────
 * Recurring application-form answers — work auth, salary, notice period,
 * diversity self-ID, boilerplate prose. The "1Password for job applications".
 * Read by the per-job copy panel; will eventually drive Playwright autofill.
 * See docs/AUTOFILL_ROADMAP.md.
 */

function QASelect({ label, value, onChange, options }: {
  label: string
  value: string
  onChange: (v: string) => void
  options: { value: string; label: string }[]
}) {
  return (
    <div>
      <p className="label">{label}</p>
      <select className="input text-xs" value={value} onChange={e => onChange(e.target.value)}>
        {options.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
      </select>
    </div>
  )
}

function QAText({ label, value, onChange, placeholder, type = 'text' }: {
  label: string
  value: string
  onChange: (v: string) => void
  placeholder?: string
  type?: string
}) {
  return (
    <div>
      <p className="label">{label}</p>
      <input
        type={type}
        className="input text-xs"
        value={value}
        onChange={e => onChange(e.target.value)}
        placeholder={placeholder}
      />
    </div>
  )
}

function QANumber({ label, value, onChange, placeholder }: {
  label: string
  value: number | null
  onChange: (v: number | null) => void
  placeholder?: string
}) {
  return (
    <div>
      <p className="label">{label}</p>
      <input
        type="number"
        className="input text-xs"
        value={value ?? ''}
        onChange={e => onChange(e.target.value === '' ? null : Number(e.target.value))}
        placeholder={placeholder}
      />
    </div>
  )
}

function QATextarea({ label, value, onChange, rows = 3, placeholder }: {
  label: string
  value: string
  onChange: (v: string) => void
  rows?: number
  placeholder?: string
}) {
  return (
    <div>
      <p className="label">{label}</p>
      <textarea
        className="input text-xs resize-none"
        rows={rows}
        value={value}
        onChange={e => onChange(e.target.value)}
        placeholder={placeholder}
      />
    </div>
  )
}

const YES_NO_UNSURE = [
  { value: 'yes', label: 'Yes' },
  { value: 'no', label: 'No' },
  { value: 'unsure', label: 'Unsure' },
]

const EEO_DECLINE = [
  { value: 'decline', label: 'Decline to state' },
  { value: 'male', label: 'Male' },
  { value: 'female', label: 'Female' },
  { value: 'non-binary', label: 'Non-binary' },
  { value: 'other', label: 'Other / self-describe' },
]

function QuickAnswersSection() {
  const qc = useQueryClient()
  const { data: qa } = useQuery({ queryKey: ['quick-answers'], queryFn: quickAnswersApi.get })
  const [draft, setDraft] = useState<QuickAnswersPatch>({})
  const [expanded, setExpanded] = useState(false)

  const saveMutation = useMutation({
    mutationFn: (patch: QuickAnswersPatch) => quickAnswersApi.update(patch),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['quick-answers'] })
      setDraft({})
    },
  })

  const reseedMutation = useMutation({
    mutationFn: quickAnswersApi.reseedFromCv,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['quick-answers'] })
      setDraft({})
    },
  })

  if (!qa) return null
  const data: QuickAnswersData = {
    ...qa.data,
    ...draft,
    identity: { ...qa.data.identity, ...(draft.identity || {}) },
    work_auth: { ...qa.data.work_auth, ...(draft.work_auth || {}) },
    compensation: { ...qa.data.compensation, ...(draft.compensation || {}) },
    logistics: { ...qa.data.logistics, ...(draft.logistics || {}) },
    background: { ...qa.data.background, ...(draft.background || {}) },
    eeo: { ...qa.data.eeo, ...(draft.eeo || {}) },
    boilerplate: { ...qa.data.boilerplate, ...(draft.boilerplate || {}) },
  }

  const dirty = Object.keys(draft).length > 0
  const setSec = <K extends keyof QuickAnswersPatch>(section: K, patch: QuickAnswersPatch[K]) =>
    setDraft(d => ({ ...d, [section]: { ...(d[section] || {}), ...patch } }))

  return (
    <section>
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-sm font-semibold text-slate-700 dark:text-slate-300 flex items-center gap-2">
          <ClipboardList size={14} className="text-carrera-600 dark:text-carrera-400" />
          Quick Answers
          <span className="text-[10px] font-normal text-slate-400">
            for application-form auto-fill
          </span>
        </h2>
        <div className="flex gap-2">
          <button
            onClick={() => reseedMutation.mutate()}
            disabled={reseedMutation.isPending}
            className="btn-secondary text-xs"
            title="Re-derive empty fields from your default CV"
          >
            <RefreshCw size={12} className={clsx(reseedMutation.isPending && 'animate-spin')} />
            Sync from CV
          </button>
          {dirty && (
            <button
              onClick={() => saveMutation.mutate(draft)}
              disabled={saveMutation.isPending}
              className="btn-primary text-xs"
            >
              <Save size={12} /> Save
            </button>
          )}
          <button
            onClick={() => setExpanded(e => !e)}
            className="btn-secondary text-xs"
          >
            {expanded ? <><ChevronUp size={12} /> Collapse</> : <><ChevronDown size={12} /> Expand</>}
          </button>
        </div>
      </div>

      {!expanded ? (
        <div className="card p-4">
          <p className="text-xs text-slate-600 dark:text-slate-400">
            The recurring questions every application form asks — work authorization, salary,
            notice period, diversity self-ID, "tell me about yourself". Filled once here, reused
            on every job. <button onClick={() => setExpanded(true)} className="text-carrera-600 dark:text-carrera-400 underline hover:no-underline">Open the editor →</button>
          </p>
        </div>
      ) : (
        <div className="space-y-4">
          {/* Identity */}
          <div className="card p-4 space-y-3">
            <h3 className="text-xs font-semibold text-slate-700 dark:text-slate-300 uppercase tracking-wide">Identity</h3>
            <div className="grid grid-cols-2 gap-3">
              <QAText label="Full name" value={data.identity.full_name} onChange={v => setSec('identity', { full_name: v })} />
              <QAText label="Preferred name" value={data.identity.preferred_name} onChange={v => setSec('identity', { preferred_name: v })} placeholder="optional" />
              <QAText label="Email" value={data.identity.email} onChange={v => setSec('identity', { email: v })} />
              <QAText label="Phone" value={data.identity.phone} onChange={v => setSec('identity', { phone: v })} />
              <QAText label="Current city" value={data.identity.current_city} onChange={v => setSec('identity', { current_city: v })} />
              <QAText label="Current country" value={data.identity.current_country} onChange={v => setSec('identity', { current_country: v })} />
              <QAText label="LinkedIn" value={data.identity.linkedin} onChange={v => setSec('identity', { linkedin: v })} placeholder="linkedin.com/in/..." />
              <QAText label="Website" value={data.identity.website} onChange={v => setSec('identity', { website: v })} placeholder="optional" />
              <QAText label="GitHub" value={data.identity.github} onChange={v => setSec('identity', { github: v })} placeholder="optional" />
              <QAText label="Pronouns" value={data.identity.pronouns} onChange={v => setSec('identity', { pronouns: v })} placeholder="he/him, she/her, they/them" />
            </div>
          </div>

          {/* Work auth */}
          <div className="card p-4 space-y-3">
            <h3 className="text-xs font-semibold text-slate-700 dark:text-slate-300 uppercase tracking-wide">Work Authorization</h3>
            <div className="grid grid-cols-2 gap-3">
              <QAText label="Citizenship" value={data.work_auth.citizenship} onChange={v => setSec('work_auth', { citizenship: v })} placeholder="e.g. Brazilian, Portuguese" />
              <QAText label="Visa status" value={data.work_auth.visa_status} onChange={v => setSec('work_auth', { visa_status: v })} placeholder="e.g. EU citizen, H-1B" />
              <QASelect label="Authorized to work in Brazil" value={data.work_auth.authorized_br} onChange={v => setSec('work_auth', { authorized_br: v })} options={YES_NO_UNSURE} />
              <QASelect label="Authorized to work in EU" value={data.work_auth.authorized_eu} onChange={v => setSec('work_auth', { authorized_eu: v })} options={YES_NO_UNSURE} />
              <QASelect label="Authorized to work in US" value={data.work_auth.authorized_us} onChange={v => setSec('work_auth', { authorized_us: v })} options={YES_NO_UNSURE} />
              <QASelect label="Authorized to work in UK" value={data.work_auth.authorized_uk} onChange={v => setSec('work_auth', { authorized_uk: v })} options={YES_NO_UNSURE} />
              <QASelect label="Sponsorship required" value={data.work_auth.sponsorship_required} onChange={v => setSec('work_auth', { sponsorship_required: v })} options={YES_NO_UNSURE} />
            </div>
          </div>

          {/* Compensation */}
          <div className="card p-4 space-y-3">
            <h3 className="text-xs font-semibold text-slate-700 dark:text-slate-300 uppercase tracking-wide">Compensation</h3>
            <div className="grid grid-cols-3 gap-3">
              <QASelect
                label="Currency"
                value={data.compensation.preferred_currency}
                onChange={v => setSec('compensation', { preferred_currency: v })}
                options={[
                  { value: 'BRL', label: 'BRL — Brazilian Real' },
                  { value: 'USD', label: 'USD — US Dollar' },
                  { value: 'EUR', label: 'EUR — Euro' },
                  { value: 'GBP', label: 'GBP — British Pound' },
                ]}
              />
              <QANumber label="Min salary (annual)" value={data.compensation.target_min_salary} onChange={v => setSec('compensation', { target_min_salary: v })} placeholder="e.g. 180000" />
              <QANumber label="Max salary (annual)" value={data.compensation.target_max_salary} onChange={v => setSec('compensation', { target_max_salary: v })} placeholder="optional" />
            </div>
            <div className="flex gap-4 text-xs">
              <label className="flex items-center gap-1.5">
                <input type="checkbox" checked={data.compensation.open_to_equity} onChange={e => setSec('compensation', { open_to_equity: e.target.checked })} />
                Open to equity
              </label>
              <label className="flex items-center gap-1.5">
                <input type="checkbox" checked={data.compensation.open_to_commission} onChange={e => setSec('compensation', { open_to_commission: e.target.checked })} />
                Open to commission
              </label>
            </div>
          </div>

          {/* Logistics */}
          <div className="card p-4 space-y-3">
            <h3 className="text-xs font-semibold text-slate-700 dark:text-slate-300 uppercase tracking-wide">Logistics</h3>
            <div className="grid grid-cols-2 gap-3">
              <QANumber label="Notice period (weeks)" value={data.logistics.notice_period_weeks} onChange={v => setSec('logistics', { notice_period_weeks: v ?? 0 })} />
              <QAText label="Earliest start date" value={data.logistics.earliest_start_date} onChange={v => setSec('logistics', { earliest_start_date: v })} placeholder="YYYY-MM-DD or e.g. 'Immediate'" />
              <QASelect
                label="Willing to relocate"
                value={data.logistics.willing_to_relocate}
                onChange={v => setSec('logistics', { willing_to_relocate: v })}
                options={[
                  { value: 'yes', label: 'Yes' },
                  { value: 'no', label: 'No' },
                  { value: 'depends', label: 'Depends on the role' },
                ]}
              />
              <QASelect
                label="Remote preference"
                value={data.logistics.remote_preference}
                onChange={v => setSec('logistics', { remote_preference: v })}
                options={[
                  { value: 'remote', label: 'Remote only' },
                  { value: 'hybrid', label: 'Hybrid' },
                  { value: 'onsite', label: 'On-site' },
                  { value: 'any', label: 'Any' },
                ]}
              />
              <QANumber label="Willing to travel (%)" value={data.logistics.willing_to_travel_pct} onChange={v => setSec('logistics', { willing_to_travel_pct: v ?? 0 })} placeholder="0–100" />
              <QANumber label="On-site days/week" value={data.logistics.onsite_days_per_week} onChange={v => setSec('logistics', { onsite_days_per_week: v ?? 0 })} placeholder="0–5" />
            </div>
          </div>

          {/* Background */}
          <div className="card p-4 space-y-3">
            <h3 className="text-xs font-semibold text-slate-700 dark:text-slate-300 uppercase tracking-wide">Background</h3>
            <div className="grid grid-cols-2 gap-3">
              <QAText label="Highest degree" value={data.background.highest_degree} onChange={v => setSec('background', { highest_degree: v })} placeholder="e.g. MBA, BSc Computer Science" />
              <QAText label="University" value={data.background.university} onChange={v => setSec('background', { university: v })} />
              <QAText label="Graduation year" value={data.background.graduation_year} onChange={v => setSec('background', { graduation_year: v })} placeholder="2018" />
              <QANumber label="Total years experience" value={data.background.total_years_experience} onChange={v => setSec('background', { total_years_experience: v ?? 0 })} />
              <QANumber label="Years in current field" value={data.background.years_in_current_field} onChange={v => setSec('background', { years_in_current_field: v ?? 0 })} />
            </div>
          </div>

          {/* EEO */}
          <div className="card p-4 space-y-3">
            <h3 className="text-xs font-semibold text-slate-700 dark:text-slate-300 uppercase tracking-wide">
              Voluntary Self-Identification
              <span className="text-[10px] text-slate-400 normal-case font-normal ml-2">(US-style EEO; always optional)</span>
            </h3>
            <div className="grid grid-cols-2 gap-3">
              <QASelect label="Gender" value={data.eeo.gender} onChange={v => setSec('eeo', { gender: v })} options={EEO_DECLINE} />
              <QASelect
                label="Race / ethnicity"
                value={data.eeo.race_ethnicity}
                onChange={v => setSec('eeo', { race_ethnicity: v })}
                options={[
                  { value: 'decline', label: 'Decline to state' },
                  { value: 'white', label: 'White' },
                  { value: 'black', label: 'Black or African American' },
                  { value: 'hispanic', label: 'Hispanic or Latino' },
                  { value: 'asian', label: 'Asian' },
                  { value: 'native', label: 'Native / Indigenous' },
                  { value: 'two-or-more', label: 'Two or more' },
                  { value: 'other', label: 'Other' },
                ]}
              />
              <QASelect
                label="Veteran status"
                value={data.eeo.veteran_status}
                onChange={v => setSec('eeo', { veteran_status: v })}
                options={[
                  { value: 'decline', label: 'Decline to state' },
                  { value: 'not-veteran', label: 'Not a veteran' },
                  { value: 'veteran', label: 'Veteran' },
                ]}
              />
              <QASelect
                label="Disability status"
                value={data.eeo.disability_status}
                onChange={v => setSec('eeo', { disability_status: v })}
                options={[
                  { value: 'decline', label: 'Decline to state' },
                  { value: 'no', label: 'No disability' },
                  { value: 'yes', label: 'Yes, I have a disability' },
                ]}
              />
            </div>
          </div>

          {/* Boilerplate */}
          <div className="card p-4 space-y-3">
            <h3 className="text-xs font-semibold text-slate-700 dark:text-slate-300 uppercase tracking-wide">Boilerplate Prose</h3>
            <p className="text-[11px] text-slate-400 dark:text-slate-500">
              Canned answers used as fallback when there's no per-job version. Carrera will override with a job-specific draft when you Tailor a resume.
            </p>
            <QATextarea label="Elevator pitch (2–3 sentences)" value={data.boilerplate.elevator_pitch} onChange={v => setSec('boilerplate', { elevator_pitch: v })} rows={3} />
            <QATextarea label='"Tell me about yourself"' value={data.boilerplate.tell_me_about_yourself} onChange={v => setSec('boilerplate', { tell_me_about_yourself: v })} rows={4} />
            <QATextarea label='"Why are you looking for a new role?"' value={data.boilerplate.why_looking} onChange={v => setSec('boilerplate', { why_looking: v })} rows={3} />
            <div className="grid grid-cols-2 gap-3">
              <QATextarea label="Biggest strength" value={data.boilerplate.biggest_strength} onChange={v => setSec('boilerplate', { biggest_strength: v })} rows={3} />
              <QATextarea label="Biggest weakness" value={data.boilerplate.biggest_weakness} onChange={v => setSec('boilerplate', { biggest_weakness: v })} rows={3} />
            </div>
          </div>
        </div>
      )}
    </section>
  )
}

export default function Settings() {
  const qc = useQueryClient()
  const [newName, setNewName] = useState('')

  const { data: profiles = [] } = useQuery({ queryKey: ['profiles'], queryFn: profilesApi.list })

  const createMutation = useMutation({
    mutationFn: (name: string) => profilesApi.create({ name }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['profiles'] })
      setNewName('')
    },
  })

  return (
    <div className="max-w-2xl space-y-6">
      <div>
        <h1 className="text-xl font-bold text-slate-900 dark:text-slate-100">Settings</h1>
        <p className="text-sm text-slate-500 dark:text-slate-400">AI provider, search profiles, and scoring configuration</p>
      </div>

      {/* AI provider keys */}
      <AIProviderSection />

      {/* Quick Answers — recurring application-form answers */}
      <QuickAnswersSection />

      {/* Search profiles */}
      <section>
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-sm font-semibold text-slate-700 dark:text-slate-300">Search Profiles</h2>
        </div>

        <div className="space-y-3 mb-4">
          {profiles.map(p => (
            <ProfileEditor key={p.id} profile={p} />
          ))}
        </div>

        <div className="flex gap-2">
          <input
            className="input text-sm flex-1"
            value={newName}
            onChange={e => setNewName(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && newName.trim() && createMutation.mutate(newName)}
            placeholder="New profile name..."
          />
          <button
            onClick={() => newName.trim() && createMutation.mutate(newName)}
            disabled={!newName.trim() || createMutation.isPending}
            className="btn-primary text-xs"
          >
            <Plus size={13} /> Create Profile
          </button>
        </div>
      </section>
    </div>
  )
}

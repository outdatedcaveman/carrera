import { useRef, useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  Save, Plus, Trash2, ChevronDown, ChevronUp, Eye, Globe, FileText,
  Sparkles, Info, Upload, Linkedin, CheckCircle2, Loader2, AlertTriangle, Languages,
} from 'lucide-react'
import { Link } from 'react-router-dom'
import clsx from 'clsx'
import { resumesApi, type ResumeImportResult } from '../api/resumes'
import type { BaseResume, CVData, CVExperience, CVEducation } from '../types'
import ResumePreview from '../components/ResumePreview'

function BulletEditor({ bullets, onChange }: { bullets: string[]; onChange: (b: string[]) => void }) {
  const update = (i: number, val: string) => {
    const next = [...bullets]
    next[i] = val
    onChange(next)
  }
  return (
    <div className="space-y-1">
      {bullets.map((b, i) => (
        <div key={i} className="flex gap-1">
          <input
            className="input text-xs flex-1"
            value={b}
            onChange={e => update(i, e.target.value)}
          />
          <button onClick={() => onChange(bullets.filter((_, j) => j !== i))} className="btn-danger p-1">
            <Trash2 size={11} />
          </button>
        </div>
      ))}
      <button
        onClick={() => onChange([...bullets, ''])}
        className="text-xs text-carrera-600 hover:text-carrera-700 flex items-center gap-1 mt-1"
      >
        <Plus size={11} /> Add bullet
      </button>
    </div>
  )
}

function ExperienceEditor({ exp, onChange, onRemove }: {
  exp: CVExperience
  onChange: (e: CVExperience) => void
  onRemove: () => void
}) {
  const [expanded, setExpanded] = useState(true)
  const set = (patch: Partial<CVExperience>) => onChange({ ...exp, ...patch })

  return (
    <div className="border border-slate-200 dark:border-slate-700 rounded-lg overflow-hidden">
      <div
        className="flex items-center justify-between px-3 py-2 bg-slate-50 dark:bg-slate-800 cursor-pointer"
        onClick={() => setExpanded(e => !e)}
      >
        <span className="text-xs font-medium text-slate-700 dark:text-slate-300">
          {exp.title || 'Untitled'} — {exp.company || 'Company'}
        </span>
        <div className="flex items-center gap-1" onClick={e => e.stopPropagation()}>
          <button onClick={onRemove} className="btn-danger p-1"><Trash2 size={11} /></button>
          {expanded ? <ChevronUp size={13} className="text-slate-400" /> : <ChevronDown size={13} className="text-slate-400" />}
        </div>
      </div>
      {expanded && (
        <div className="p-3 space-y-2">
          <div className="grid grid-cols-2 gap-2">
            <div>
              <p className="label">Title</p>
              <input className="input text-xs" value={exp.title} onChange={e => set({ title: e.target.value })} />
            </div>
            <div>
              <p className="label">Company</p>
              <input className="input text-xs" value={exp.company} onChange={e => set({ company: e.target.value })} />
            </div>
            <div>
              <p className="label">Start</p>
              <input className="input text-xs" value={exp.start_date} onChange={e => set({ start_date: e.target.value })} placeholder="2022-01" />
            </div>
            <div>
              <p className="label">End (blank = current)</p>
              <input className="input text-xs" value={exp.end_date ?? ''} onChange={e => set({ end_date: e.target.value || null })} placeholder="2024-06" />
            </div>
          </div>
          <div>
            <p className="label">Bullets</p>
            <BulletEditor bullets={exp.bullets} onChange={b => set({ bullets: b })} />
          </div>
        </div>
      )}
    </div>
  )
}

function EducationEditor({ edu, onChange, onRemove }: {
  edu: CVEducation
  onChange: (e: CVEducation) => void
  onRemove: () => void
}) {
  const [expanded, setExpanded] = useState(true)
  const set = (patch: Partial<CVEducation>) => onChange({ ...edu, ...patch })

  return (
    <div className="border border-slate-200 dark:border-slate-700 rounded-lg overflow-hidden">
      <div
        className="flex items-center justify-between px-3 py-2 bg-slate-50 dark:bg-slate-800 cursor-pointer"
        onClick={() => setExpanded(e => !e)}
      >
        <span className="text-xs font-medium text-slate-700 dark:text-slate-300">
          {edu.degree || 'Degree'} — {edu.institution || 'Institution'}
        </span>
        <div className="flex items-center gap-1" onClick={e => e.stopPropagation()}>
          <button onClick={onRemove} className="btn-danger p-1"><Trash2 size={11} /></button>
          {expanded ? <ChevronUp size={13} className="text-slate-400" /> : <ChevronDown size={13} className="text-slate-400" />}
        </div>
      </div>
      {expanded && (
        <div className="p-3 space-y-2">
          <div className="grid grid-cols-2 gap-2">
            <div>
              <p className="label">Institution</p>
              <input className="input text-xs" value={edu.institution} onChange={e => set({ institution: e.target.value })} />
            </div>
            <div>
              <p className="label">Degree</p>
              <input className="input text-xs" value={edu.degree} onChange={e => set({ degree: e.target.value })} placeholder="BSc, MBA, …" />
            </div>
            <div>
              <p className="label">Field of Study</p>
              <input className="input text-xs" value={edu.field} onChange={e => set({ field: e.target.value })} />
            </div>
            <div className="grid grid-cols-2 gap-2">
              <div>
                <p className="label">Start</p>
                <input className="input text-xs" value={edu.start_date} onChange={e => set({ start_date: e.target.value })} placeholder="2018" />
              </div>
              <div>
                <p className="label">End</p>
                <input className="input text-xs" value={edu.end_date ?? ''} onChange={e => set({ end_date: e.target.value || null })} placeholder="2022" />
              </div>
            </div>
          </div>
          <div>
            <p className="label">Notes (honors, GPA, thesis, …)</p>
            <textarea
              className="input text-xs resize-none"
              rows={2}
              value={edu.notes}
              onChange={e => set({ notes: e.target.value })}
            />
          </div>
        </div>
      )}
    </div>
  )
}

function ListEditor({ items, onChange, placeholder }: {
  items: string[]
  onChange: (v: string[]) => void
  placeholder?: string
}) {
  const update = (i: number, val: string) => {
    const next = [...items]
    next[i] = val
    onChange(next)
  }
  return (
    <div className="space-y-1">
      {items.map((b, i) => (
        <div key={i} className="flex gap-1">
          <input
            className="input text-xs flex-1"
            value={b}
            onChange={e => update(i, e.target.value)}
            placeholder={placeholder}
          />
          <button onClick={() => onChange(items.filter((_, j) => j !== i))} className="btn-danger p-1">
            <Trash2 size={11} />
          </button>
        </div>
      ))}
      <button
        onClick={() => onChange([...items, ''])}
        className="text-xs text-carrera-600 hover:text-carrera-700 flex items-center gap-1 mt-1"
      >
        <Plus size={11} /> Add
      </button>
    </div>
  )
}

function ResumeForm({ resume, onSaved }: { resume: BaseResume; onSaved: () => void }) {
  const qc = useQueryClient()
  const [cv, setCv] = useState<CVData>(resume.data)
  const [preview, setPreview] = useState(false)
  const [dirty, setDirty] = useState(false)
  const [confirmDelete, setConfirmDelete] = useState(false)

  const set = (patch: Partial<CVData>) => { setCv(c => ({ ...c, ...patch })); setDirty(true) }

  const saveMutation = useMutation({
    mutationFn: () => resumesApi.update(resume.id, { data: cv }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['resumes'] })
      setDirty(false)
      onSaved()
    },
  })

  const setDefaultMutation = useMutation({
    mutationFn: () => resumesApi.update(resume.id, { is_default: true }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['resumes'] }),
  })

  // Translate this CV to the *other* language. Creates a new resume rather
  // than mutating this one — user keeps both for cross-language applications.
  const otherLang: 'en' | 'pt' = resume.language === 'en' ? 'pt' : 'en'
  const translateMutation = useMutation({
    mutationFn: () => resumesApi.translate(resume.id, { target_language: otherLang }),
    onSuccess: (newResume) => {
      qc.invalidateQueries({ queryKey: ['resumes'] })
      // Hint to parent to switch — but parent owns selection; emit via onSaved.
      // The new resume will appear in the tab bar.
      void newResume
    },
  })

  const deleteMutation = useMutation({
    mutationFn: () => resumesApi.delete(resume.id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['resumes'] })
      setConfirmDelete(false)
    },
  })

  const updateExp = (i: number, exp: CVExperience) => {
    const next = [...cv.experience]
    next[i] = exp
    set({ experience: next })
  }

  const removeExp = (i: number) => set({ experience: cv.experience.filter((_, j) => j !== i) })

  const addExp = () => set({
    experience: [{
      company: '', title: '', start_date: '', end_date: null,
      location: '', bullets: [], keywords: [],
    }, ...cv.experience],
  })

  const updateEdu = (i: number, edu: CVEducation) => {
    const next = [...cv.education]
    next[i] = edu
    set({ education: next })
  }
  const removeEdu = (i: number) => set({ education: cv.education.filter((_, j) => j !== i) })
  const addEdu = () => set({
    education: [{
      institution: '', degree: '', field: '', start_date: '', end_date: null, notes: '',
    }, ...cv.education],
  })

  const updateLang = (i: number, lang: { language: string; level: string }) => {
    const next = [...cv.languages]
    next[i] = lang
    set({ languages: next })
  }
  const removeLang = (i: number) => set({ languages: cv.languages.filter((_, j) => j !== i) })
  const addLang = () => set({ languages: [...cv.languages, { language: '', level: 'Fluent' }] })

  if (preview) {
    return (
      <div>
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-sm font-semibold text-slate-700 dark:text-slate-300">Preview — {resume.name}</h3>
          <button onClick={() => setPreview(false)} className="btn-secondary text-xs">← Edit</button>
        </div>
        <ResumePreview cv={cv} />
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-slate-700 dark:text-slate-300 flex items-center gap-2">
          {resume.name}
          <span className="badge bg-slate-100 dark:bg-slate-700 text-slate-500 text-[10px]">v{resume.version}</span>
          <Globe size={12} className="text-slate-400" />
          <span className="text-[10px] text-slate-400">{resume.language.toUpperCase()}</span>
          {resume.is_default && (
            <span className="text-[9px] uppercase tracking-wide text-carrera-600 dark:text-carrera-400">default</span>
          )}
        </h3>
        <div className="flex gap-2">
          <button onClick={() => setPreview(true)} className="btn-secondary text-xs">
            <Eye size={12} /> Preview
          </button>
          <button
            onClick={() => translateMutation.mutate()}
            disabled={translateMutation.isPending}
            className="btn-secondary text-xs"
            title={`Generate a ${otherLang.toUpperCase()} twin of this CV via the configured LLM`}
          >
            {translateMutation.isPending ? (
              <><Loader2 size={12} className="animate-spin" /> Translating…</>
            ) : (
              <><Languages size={12} /> Translate to {otherLang.toUpperCase()}</>
            )}
          </button>
          {!resume.is_default && (
            <button
              onClick={() => setDefaultMutation.mutate()}
              disabled={setDefaultMutation.isPending}
              className="btn-secondary text-xs"
              title={`Make this the default CV for ${resume.language.toUpperCase()}`}
            >
              <Globe size={12} /> Set as default
            </button>
          )}
          {!resume.is_default && (
            <button
              onClick={() => setConfirmDelete(true)}
              className="btn-danger text-xs"
              title="Delete this CV"
            >
              <Trash2 size={12} /> Delete
            </button>
          )}
          {dirty && (
            <button onClick={() => saveMutation.mutate()} disabled={saveMutation.isPending} className="btn-primary text-xs">
              <Save size={12} /> Save
            </button>
          )}
        </div>
      </div>

      {translateMutation.error && (() => {
        const msg = (translateMutation.error as Error).message
        const isKey = msg.includes('API key') && msg.includes('not configured')
        const isCredit = /credit|balance|billing|quota|insufficient/i.test(msg)
        const isAuth = /authentication|invalid.*api.*key|unauthorized|401/i.test(msg)
        return (
          <div className="card p-3 text-xs text-red-600 dark:text-red-400 bg-red-50 dark:bg-red-950/30 border-red-200 dark:border-red-900">
            {isKey ? (
              <>Translation needs an LLM key. <Link to="/settings" className="underline">Set one in Settings → AI Provider</Link>.</>
            ) : isCredit ? (
              <>
                <p className="font-medium">Your AI provider account is out of credits.</p>
                <p className="mt-1">{msg}</p>
                <p className="mt-1">
                  Add credits at{' '}
                  <a className="underline" href="https://console.anthropic.com/settings/billing" target="_blank" rel="noopener noreferrer">console.anthropic.com/settings/billing</a>
                  {' '}or{' '}
                  <a className="underline" href="https://platform.openai.com/account/billing" target="_blank" rel="noopener noreferrer">platform.openai.com/account/billing</a>.
                </p>
              </>
            ) : isAuth ? (
              <>
                <p className="font-medium">The API key is invalid or unauthorized.</p>
                <p className="mt-1">{msg}</p>
                <p className="mt-1"><Link to="/settings" className="underline">Replace it in Settings → AI Provider</Link>.</p>
              </>
            ) : (
              msg
            )}
          </div>
        )
      })()}

      {/* Delete-confirm modal */}
      {confirmDelete && (
        <div className="card p-4 bg-red-50/70 dark:bg-red-950/30 border-red-200 dark:border-red-900">
          <p className="text-sm text-slate-800 dark:text-slate-200 font-medium mb-1">
            Delete "{resume.name}"?
          </p>
          <p className="text-xs text-slate-500 dark:text-slate-400 mb-3">
            This can't be undone. Tailored applications already produced from it
            will keep their snapshot.
          </p>
          <div className="flex gap-2">
            <button
              onClick={() => deleteMutation.mutate()}
              disabled={deleteMutation.isPending}
              className="btn-danger text-xs"
            >
              <Trash2 size={12} /> Yes, delete
            </button>
            <button onClick={() => setConfirmDelete(false)} className="btn-secondary text-xs">
              Cancel
            </button>
            {deleteMutation.error && (
              <span className="text-xs text-red-600 dark:text-red-400 self-center">
                {(deleteMutation.error as Error).message}
              </span>
            )}
          </div>
        </div>
      )}

      {/* Personal info */}
      <div className="card p-4 space-y-3">
        <h4 className="text-xs font-semibold text-slate-700 dark:text-slate-300 uppercase tracking-wide">Personal Info</h4>
        <div className="grid grid-cols-2 gap-3">
          {(['full_name', 'email', 'phone', 'location', 'linkedin', 'website'] as const).map(field => (
            <div key={field}>
              <p className="label capitalize">{field.replace('_', ' ')}</p>
              <input
                className="input text-xs"
                value={cv[field] as string}
                onChange={e => set({ [field]: e.target.value })}
              />
            </div>
          ))}
        </div>
      </div>

      {/* Summary */}
      <div className="card p-4">
        <p className="label">Professional Summary</p>
        <textarea
          className="input text-xs resize-none"
          rows={4}
          value={cv.summary}
          onChange={e => set({ summary: e.target.value })}
        />
      </div>

      {/* Experience */}
      <div className="card p-4 space-y-3">
        <div className="flex items-center justify-between">
          <h4 className="text-xs font-semibold text-slate-700 dark:text-slate-300 uppercase tracking-wide">Experience</h4>
          <button onClick={addExp} className="btn-secondary text-xs"><Plus size={11} /> Add Role</button>
        </div>
        {cv.experience.map((exp, i) => (
          <ExperienceEditor key={i} exp={exp} onChange={e => updateExp(i, e)} onRemove={() => removeExp(i)} />
        ))}
      </div>

      {/* Education */}
      <div className="card p-4 space-y-3">
        <div className="flex items-center justify-between">
          <h4 className="text-xs font-semibold text-slate-700 dark:text-slate-300 uppercase tracking-wide">Education</h4>
          <button onClick={addEdu} className="btn-secondary text-xs"><Plus size={11} /> Add Degree</button>
        </div>
        {cv.education.length === 0 && (
          <p className="text-xs text-slate-400 dark:text-slate-500 italic">No education entries yet.</p>
        )}
        {cv.education.map((edu, i) => (
          <EducationEditor key={i} edu={edu} onChange={e => updateEdu(i, e)} onRemove={() => removeEdu(i)} />
        ))}
      </div>

      {/* Skills */}
      <div className="card p-4 space-y-2">
        <h4 className="text-xs font-semibold text-slate-700 dark:text-slate-300 uppercase tracking-wide">Skills</h4>
        <p className="text-[11px] text-slate-400 dark:text-slate-500">Comma-separated — Carrera matches these against job postings.</p>
        <textarea
          className="input text-xs resize-none"
          rows={3}
          value={cv.skills.join(', ')}
          onChange={e => set({ skills: e.target.value.split(',').map(s => s.trim()).filter(Boolean) })}
          placeholder="Python, FastAPI, React, SQL, …"
        />
      </div>

      {/* Languages */}
      <div className="card p-4 space-y-3">
        <div className="flex items-center justify-between">
          <h4 className="text-xs font-semibold text-slate-700 dark:text-slate-300 uppercase tracking-wide">Languages</h4>
          <button onClick={addLang} className="btn-secondary text-xs"><Plus size={11} /> Add Language</button>
        </div>
        {cv.languages.length === 0 && (
          <p className="text-xs text-slate-400 dark:text-slate-500 italic">No languages yet.</p>
        )}
        {cv.languages.map((lang, i) => (
          <div key={i} className="flex gap-2 items-end">
            <div className="flex-1">
              <p className="label">Language</p>
              <input
                className="input text-xs"
                value={lang.language}
                onChange={e => updateLang(i, { ...lang, language: e.target.value })}
                placeholder="English"
              />
            </div>
            <div className="flex-1">
              <p className="label">Level</p>
              <select
                className="input text-xs"
                value={lang.level}
                onChange={e => updateLang(i, { ...lang, level: e.target.value })}
              >
                <option value="Native">Native</option>
                <option value="Fluent">Fluent</option>
                <option value="Intermediate">Intermediate</option>
                <option value="Basic">Basic</option>
              </select>
            </div>
            <button onClick={() => removeLang(i)} className="btn-danger p-2 mb-px"><Trash2 size={11} /></button>
          </div>
        ))}
      </div>

      {/* Certifications, Awards & Distinctions */}
      <div className="card p-4 space-y-2">
        <h4 className="text-xs font-semibold text-slate-700 dark:text-slate-300 uppercase tracking-wide">
          Certifications, Awards & Distinctions
        </h4>
        <p className="text-[11px] text-slate-400 dark:text-slate-500">
          One per line — e.g. "AWS Solutions Architect — Amazon (2023)" or "Dean's List 2021".
        </p>
        <ListEditor
          items={cv.certifications}
          onChange={v => set({ certifications: v })}
          placeholder="Certification, award, or distinction"
        />
      </div>
    </div>
  )
}

const EMPTY_CV: CVData = {
  full_name: '',
  email: '',
  phone: '',
  location: '',
  linkedin: '',
  website: '',
  summary: '',
  experience: [],
  education: [],
  skills: [],
  languages: [],
  certifications: [],
  extra_sections: {},
}

/** Inline file-picker that uploads a CV PDF or a LinkedIn data-export ZIP.
 *
 *  Not a modal — we drop it straight into the page so the flow is one click
 *  → pick file → import lands as a new editable resume. A short confirmation
 *  toast appears via `onDone`.
 */
function ImportCV({
  defaultLanguage,
  makeDefault,
  onDone,
}: {
  defaultLanguage: 'en' | 'pt'
  makeDefault: boolean
  onDone: (result: ResumeImportResult) => void
}) {
  const qc = useQueryClient()
  const pdfInputRef = useRef<HTMLInputElement>(null)
  const zipInputRef = useRef<HTMLInputElement>(null)
  const [language, setLanguage] = useState<'en' | 'pt'>(defaultLanguage)

  const mutation = useMutation({
    mutationFn: async (file: File) => {
      const isZip = file.name.toLowerCase().endsWith('.zip')
      const friendly = isZip ? 'Imported from LinkedIn' : file.name.replace(/\.pdf$/i, '')
      return resumesApi.import({
        file,
        name: `${friendly} (${language.toUpperCase()})`,
        language,
        isDefault: makeDefault,
      })
    },
    onSuccess: (result) => {
      qc.invalidateQueries({ queryKey: ['resumes'] })
      onDone(result)
    },
  })

  const handlePick = (file: File | null | undefined) => {
    if (!file) return
    mutation.mutate(file)
  }

  return (
    <div className="card p-4 space-y-3 border-carrera-100 dark:border-carrera-900 bg-carrera-50/40 dark:bg-carrera-900/10">
      <div className="flex items-center gap-2">
        <Sparkles size={14} className="text-carrera-600 dark:text-carrera-400" />
        <p className="text-sm font-semibold text-slate-800 dark:text-slate-200">
          Import your CV in one click
        </p>
      </div>
      <p className="text-xs text-slate-600 dark:text-slate-400">
        Upload a <strong>PDF</strong> and we'll parse it into the right fields with AI.
        Or drop in your <strong>LinkedIn data-export ZIP</strong> (from{' '}
        <em>Settings &rarr; Data privacy &rarr; Get a copy of your data</em>) and we'll read the CSVs
        inside — no login, no TOS risk.
      </p>

      <div className="flex items-center gap-2 text-[11px]">
        <span className="text-slate-500 dark:text-slate-400">Language:</span>
        <button
          onClick={() => setLanguage('en')}
          className={clsx(
            'px-2 py-0.5 rounded border',
            language === 'en'
              ? 'bg-carrera-600 text-white border-carrera-600'
              : 'border-slate-200 dark:border-slate-700 text-slate-600 dark:text-slate-300',
          )}
        >
          English
        </button>
        <button
          onClick={() => setLanguage('pt')}
          className={clsx(
            'px-2 py-0.5 rounded border',
            language === 'pt'
              ? 'bg-carrera-600 text-white border-carrera-600'
              : 'border-slate-200 dark:border-slate-700 text-slate-600 dark:text-slate-300',
          )}
        >
          Português
        </button>
      </div>

      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          onClick={() => pdfInputRef.current?.click()}
          disabled={mutation.isPending}
          className="btn-primary text-xs"
        >
          {mutation.isPending ? <Loader2 size={12} className="animate-spin" /> : <Upload size={12} />}
          Upload PDF
        </button>
        <input
          ref={pdfInputRef}
          type="file"
          accept="application/pdf,.pdf"
          className="hidden"
          onChange={e => {
            handlePick(e.target.files?.[0])
            e.target.value = ''
          }}
        />

        <button
          type="button"
          onClick={() => zipInputRef.current?.click()}
          disabled={mutation.isPending}
          className="btn-secondary text-xs"
        >
          {mutation.isPending ? <Loader2 size={12} className="animate-spin" /> : <Linkedin size={12} />}
          Import LinkedIn ZIP
        </button>
        <input
          ref={zipInputRef}
          type="file"
          accept=".zip,application/zip,application/x-zip-compressed"
          className="hidden"
          onChange={e => {
            handlePick(e.target.files?.[0])
            e.target.value = ''
          }}
        />
      </div>

      {mutation.isPending && (
        <p className="text-[11px] text-slate-500 dark:text-slate-400">
          Parsing{mutation.variables?.name?.toLowerCase().endsWith('.pdf') ? ' with AI' : ''}…
          this takes ~10 seconds for a PDF.
        </p>
      )}
      {mutation.error && (
        <p className="text-xs text-red-600 dark:text-red-400">
          Import failed: {mutation.error.message}
        </p>
      )}
    </div>
  )
}

function ImportResultToast({
  result,
  onDismiss,
}: {
  result: ResumeImportResult
  onDismiss: () => void
}) {
  const s = result.summary
  const src = result.source === 'linkedin' ? 'LinkedIn archive' : 'PDF'
  const isHeuristic = result.parser === 'heuristic'
  const everythingZero = s.experience_count === 0 && s.education_count === 0 && s.skills_count === 0

  // When the heuristic ran (no LLM key), only basic regex fields got filled —
  // warn loudly and point the user at Settings.
  if (isHeuristic) {
    return (
      <div className="card p-3 flex items-start gap-3 bg-amber-50/70 dark:bg-amber-900/20 border-amber-200 dark:border-amber-900">
        <AlertTriangle size={16} className="text-amber-600 dark:text-amber-400 shrink-0 mt-0.5" />
        <div className="flex-1 text-xs text-slate-700 dark:text-slate-300 space-y-1">
          <p className="font-semibold text-slate-800 dark:text-slate-200">
            Imported {result.resume.name}, but only the basics — no AI provider configured.
          </p>
          <p className="text-slate-500 dark:text-slate-400">
            Got name / email / phone / LinkedIn from the PDF, but{' '}
            <strong>experience, education, and skills require an LLM</strong> to parse.{' '}
            <Link to="/settings" className="text-carrera-600 dark:text-carrera-400 underline hover:no-underline">
              Add an Anthropic or OpenAI API key in Settings
            </Link>{' '}
            and re-import — it costs ~$0.001 per CV on Haiku.
          </p>
          {!everythingZero && (
            <p className="text-slate-400 dark:text-slate-500 text-[11px]">
              Heuristic also caught: {s.experience_count} position{s.experience_count === 1 ? '' : 's'}, {s.education_count} education,{' '}
              {s.skills_count} skill{s.skills_count === 1 ? '' : 's'}.
            </p>
          )}
        </div>
        <button onClick={onDismiss} className="text-slate-400 hover:text-slate-600 text-xs shrink-0">✕</button>
      </div>
    )
  }

  return (
    <div className="card p-3 flex items-start gap-3 bg-emerald-50/70 dark:bg-emerald-900/20 border-emerald-200 dark:border-emerald-900">
      <CheckCircle2 size={16} className="text-emerald-600 dark:text-emerald-400 shrink-0 mt-0.5" />
      <div className="flex-1 text-xs text-slate-700 dark:text-slate-300">
        <p className="font-semibold text-slate-800 dark:text-slate-200">
          Imported {result.resume.name} from your {src}
          {result.parser === 'anthropic' && <span className="text-[10px] text-slate-400 font-normal ml-1.5">(via Claude)</span>}
          {result.parser === 'openai' && <span className="text-[10px] text-slate-400 font-normal ml-1.5">(via GPT)</span>}
        </p>
        <p className="text-slate-500 dark:text-slate-400 mt-0.5">
          {s.experience_count} position{s.experience_count === 1 ? '' : 's'},{' '}
          {s.education_count} education entr{s.education_count === 1 ? 'y' : 'ies'},{' '}
          {s.skills_count} skill{s.skills_count === 1 ? '' : 's'}
          {s.languages_count > 0 && `, ${s.languages_count} language${s.languages_count === 1 ? '' : 's'}`}
          {s.certifications_count > 0 && `, ${s.certifications_count} cert${s.certifications_count === 1 ? '' : 's'}`}.
          Review &amp; edit below, then save.
        </p>
      </div>
      <button onClick={onDismiss} className="text-slate-400 hover:text-slate-600 text-xs shrink-0">✕</button>
    </div>
  )
}

export default function ResumeEditor() {
  const qc = useQueryClient()
  const { data: resumes = [], isLoading } = useQuery({ queryKey: ['resumes'], queryFn: resumesApi.list })
  const [selected, setSelected] = useState<number | null>(null)
  const [helpOpen, setHelpOpen] = useState(true)
  const [importing, setImporting] = useState(false)
  const [lastImport, setLastImport] = useState<ResumeImportResult | null>(null)

  const selectedResume = resumes.find(r => r.id === selected) ?? resumes[0]

  const createMutation = useMutation({
    mutationFn: (lang: 'en' | 'pt') =>
      resumesApi.create({
        name: lang === 'pt' ? 'Meu CV (PT)' : 'My CV (EN)',
        language: lang,
        is_default: resumes.length === 0,
        data: EMPTY_CV,
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['resumes'] }),
  })

  return (
    <div className="max-w-3xl space-y-4">
      <div>
        <h1 className="text-xl font-bold text-slate-900 dark:text-slate-100 flex items-center gap-2">
          <FileText size={20} className="text-carrera-600 dark:text-carrera-500" />
          Resume Editor
        </h1>
        <p className="text-sm text-slate-500 dark:text-slate-400">Your base CV — the source Carrera tailors from.</p>
      </div>

      {/* Help banner — what is this page for? */}
      {helpOpen && resumes.length > 0 && (
        <div className="card p-4 bg-carrera-50/60 dark:bg-carrera-900/20 border-carrera-100 dark:border-carrera-900">
          <div className="flex items-start gap-3">
            <Sparkles size={16} className="text-carrera-600 dark:text-carrera-400 shrink-0 mt-0.5" />
            <div className="flex-1 text-xs text-slate-700 dark:text-slate-300 space-y-2">
              <p className="font-semibold text-slate-800 dark:text-slate-200">What is this page?</p>
              <p>
                This is your <strong>base CV</strong> — your real, complete résumé. Keep one per language (EN / PT).
                Update it whenever you take on a new responsibility or finish a project.
              </p>
              <p className="font-semibold text-slate-800 dark:text-slate-200 pt-1">How do I use it?</p>
              <ol className="list-decimal ml-4 space-y-1">
                <li>Edit the personal info, summary, experience bullets, and skills below.</li>
                <li>Go to <strong>Jobs</strong>, open any job, click <em>Tailor Resume</em>.</li>
                <li>Carrera picks the most relevant bullets, adjusts your summary, and drafts a cover letter — based on this CV.</li>
                <li>Download the tailored PDFs and apply.</li>
              </ol>
            </div>
            <button onClick={() => setHelpOpen(false)} className="text-slate-400 hover:text-slate-600 text-xs shrink-0" title="Hide">
              ✕
            </button>
          </div>
        </div>
      )}

      {/* Language tabs — always visible once there's at least one resume */}
      {resumes.length > 0 && (
        <div className="flex items-center gap-2 border-b border-slate-200 dark:border-slate-700">
          {resumes.map(r => {
            const active = (selected ?? selectedResume?.id) === r.id
            return (
              <button
                key={r.id}
                onClick={() => setSelected(r.id)}
                className={clsx(
                  'px-3 py-2 text-xs font-medium border-b-2 transition-colors -mb-px flex items-center gap-1.5',
                  active
                    ? 'border-carrera-600 text-carrera-700 dark:text-carrera-400'
                    : 'border-transparent text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-200'
                )}
              >
                <Globe size={11} />
                {r.name}
                {r.is_default && <span className="text-[9px] uppercase tracking-wide text-carrera-600 dark:text-carrera-400">default</span>}
              </button>
            )
          })}
          <div className="ml-auto flex items-center gap-2 pb-1">
            <button
              onClick={() => setImporting(v => !v)}
              className={clsx(
                'text-xs font-medium rounded-md px-2.5 py-1.5 flex items-center gap-1.5 transition-colors',
                importing
                  ? 'bg-carrera-600 text-white hover:bg-carrera-700'
                  : 'bg-carrera-50 text-carrera-700 hover:bg-carrera-100 dark:bg-carrera-900/40 dark:text-carrera-300 dark:hover:bg-carrera-900/60'
              )}
              title="Upload a PDF resume or LinkedIn data export"
            >
              <Upload size={12} /> Import PDF / LinkedIn
            </button>
            <button
              onClick={() => {
                const lang = resumes.some(r => r.language === 'en') ? 'pt' : 'en'
                createMutation.mutate(lang)
              }}
              disabled={createMutation.isPending}
              className="text-[11px] text-slate-500 hover:text-carrera-600 flex items-center gap-1"
            >
              <Plus size={11} /> New CV
            </button>
          </div>
        </div>
      )}

      {/* Import panel — collapsible, visible from both empty state and tab bar */}
      {(importing || resumes.length === 0) && !isLoading && (
        <ImportCV
          defaultLanguage={resumes.some(r => r.language === 'en') ? 'pt' : 'en'}
          makeDefault={resumes.length === 0}
          onDone={(result) => {
            setImporting(false)
            setLastImport(result)
            setSelected(result.resume.id)
          }}
        />
      )}

      {lastImport && (
        <ImportResultToast result={lastImport} onDismiss={() => setLastImport(null)} />
      )}

      {isLoading && (
        <div className="card p-8 animate-pulse">
          <div className="h-4 bg-slate-200 dark:bg-slate-700 rounded w-1/2 mb-4" />
          <div className="h-3 bg-slate-100 dark:bg-slate-800 rounded w-3/4" />
        </div>
      )}

      {/* Empty state — no resumes yet. ImportCV renders above; this shows the
          "start from scratch" fallback for people who don't want to import. */}
      {!isLoading && resumes.length === 0 && (
        <div className="card p-6 text-center space-y-3">
          <FileText size={32} className="mx-auto text-slate-300 dark:text-slate-600" />
          <div>
            <p className="text-xs text-slate-500 dark:text-slate-400 max-w-md mx-auto">
              …or start from a blank CV and type everything in.
            </p>
          </div>
          <div className="flex justify-center gap-2">
            <button
              onClick={() => createMutation.mutate('en')}
              disabled={createMutation.isPending}
              className="btn-secondary text-xs"
            >
              <Plus size={12} /> Blank English CV
            </button>
            <button
              onClick={() => createMutation.mutate('pt')}
              disabled={createMutation.isPending}
              className="btn-secondary text-xs"
            >
              <Plus size={12} /> CV em branco (PT)
            </button>
          </div>
          <p className="text-[11px] text-slate-400 dark:text-slate-600">
            <Info size={10} className="inline mr-1" />
            If this is a new installation, default seed profiles should load automatically — try restarting the app.
          </p>
        </div>
      )}

      {selectedResume && (
        <ResumeForm
          key={selectedResume.id}
          resume={selectedResume}
          onSaved={() => {}}
        />
      )}
    </div>
  )
}

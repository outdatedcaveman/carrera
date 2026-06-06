/**
 * QuickAnswersPanel — collapsible panel rendered inside JobDetail.
 *
 * Surfaces the user's saved Quick Answers as a copy-to-clipboard list,
 * organized by category and ordered by what application forms typically
 * ask first. One click copies the value; the button briefly shows a
 * checkmark so the user knows it landed.
 *
 * This is Layer 1's user-visible payoff — it makes filling a Workday or
 * Greenhouse form a row of clicks instead of a row of typing/swearing.
 * Layer 2 (job-specific drafts of free-text answers) and Layer 3
 * (Playwright autofill) will plug into the same data source. See
 * docs/AUTOFILL_ROADMAP.md.
 */
import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { ClipboardList, Copy, Check, ChevronDown, ChevronUp, Settings } from 'lucide-react'
import { Link } from 'react-router-dom'
import { quickAnswersApi } from '../api/quickAnswers'
import clsx from 'clsx'

function CopyRow({ label, value, hint }: { label: string; value: string; hint?: string }) {
  const [copied, setCopied] = useState(false)
  if (!value) return null
  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(value)
      setCopied(true)
      setTimeout(() => setCopied(false), 1200)
    } catch {
      // ignore — some webview contexts deny clipboard
    }
  }
  return (
    <button
      onClick={handleCopy}
      className="w-full text-left flex items-start gap-2 px-2 py-1.5 rounded hover:bg-slate-100 dark:hover:bg-slate-700/40 group"
    >
      <span className="shrink-0 w-32 text-[11px] text-slate-500 dark:text-slate-400 pt-px">
        {label}
      </span>
      <span className="flex-1 text-xs text-slate-700 dark:text-slate-300 break-words">
        {value}
        {hint && <span className="text-[10px] text-slate-400 ml-1.5">{hint}</span>}
      </span>
      <span className="shrink-0 text-slate-400 group-hover:text-carrera-600 dark:group-hover:text-carrera-400 mt-0.5">
        {copied ? <Check size={12} className="text-emerald-500" /> : <Copy size={12} />}
      </span>
    </button>
  )
}

function Section({ title, children, defaultOpen = false }: {
  title: string
  children: React.ReactNode
  defaultOpen?: boolean
}) {
  const [open, setOpen] = useState(defaultOpen)
  return (
    <div className="border-t border-slate-200 dark:border-slate-700 first:border-t-0">
      <button
        onClick={() => setOpen(o => !o)}
        className="w-full flex items-center justify-between px-2 py-1.5 text-[11px] font-semibold text-slate-600 dark:text-slate-400 uppercase tracking-wide hover:bg-slate-50 dark:hover:bg-slate-800/40"
      >
        {title}
        {open ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
      </button>
      {open && <div className="pb-1">{children}</div>}
    </div>
  )
}

const YN: Record<string, string> = { yes: 'Yes', no: 'No', unsure: 'Unsure' }
const RELOC: Record<string, string> = { yes: 'Yes', no: 'No', depends: 'Depends on the role' }
const REMOTE: Record<string, string> = { remote: 'Remote', hybrid: 'Hybrid', onsite: 'On-site', any: 'No preference' }

export default function QuickAnswersPanel() {
  const { data: qa } = useQuery({ queryKey: ['quick-answers'], queryFn: quickAnswersApi.get })
  const [expanded, setExpanded] = useState(false)

  if (!qa) return null
  const d = qa.data
  const salary = d.compensation.target_min_salary
    ? `${d.compensation.target_min_salary.toLocaleString()} ${d.compensation.preferred_currency}` +
      (d.compensation.target_max_salary ? ` – ${d.compensation.target_max_salary.toLocaleString()}` : '+')
    : ''

  return (
    <div className="card p-0 overflow-hidden">
      <button
        onClick={() => setExpanded(e => !e)}
        className={clsx(
          'w-full flex items-center justify-between p-3 text-left',
          expanded && 'border-b border-slate-200 dark:border-slate-700'
        )}
      >
        <span className="flex items-center gap-2">
          <ClipboardList size={14} className="text-carrera-600 dark:text-carrera-400" />
          <span className="text-xs font-semibold text-slate-700 dark:text-slate-200">Quick Answers</span>
          <span className="text-[10px] text-slate-400">click to copy</span>
        </span>
        {expanded ? <ChevronUp size={13} className="text-slate-400" /> : <ChevronDown size={13} className="text-slate-400" />}
      </button>

      {expanded && (
        <>
          <Section title="Identity" defaultOpen>
            <CopyRow label="Full name" value={d.identity.full_name} />
            <CopyRow label="Preferred name" value={d.identity.preferred_name} />
            <CopyRow label="Email" value={d.identity.email} />
            <CopyRow label="Phone" value={d.identity.phone} />
            <CopyRow label="City" value={d.identity.current_city} />
            <CopyRow label="Country" value={d.identity.current_country} />
            <CopyRow label="LinkedIn" value={d.identity.linkedin} />
            <CopyRow label="Website" value={d.identity.website} />
            <CopyRow label="GitHub" value={d.identity.github} />
            <CopyRow label="Pronouns" value={d.identity.pronouns} />
          </Section>

          <Section title="Work Authorization">
            <CopyRow label="Citizenship" value={d.work_auth.citizenship} />
            <CopyRow label="Visa status" value={d.work_auth.visa_status} />
            <CopyRow label="Auth — Brazil" value={YN[d.work_auth.authorized_br] || ''} />
            <CopyRow label="Auth — EU" value={YN[d.work_auth.authorized_eu] || ''} />
            <CopyRow label="Auth — US" value={YN[d.work_auth.authorized_us] || ''} />
            <CopyRow label="Auth — UK" value={YN[d.work_auth.authorized_uk] || ''} />
            <CopyRow label="Sponsorship needed" value={YN[d.work_auth.sponsorship_required] || ''} />
          </Section>

          <Section title="Compensation & Logistics">
            <CopyRow label="Target salary" value={salary} hint="(annual)" />
            <CopyRow label="Notice period" value={d.logistics.notice_period_weeks ? `${d.logistics.notice_period_weeks} weeks` : ''} />
            <CopyRow label="Earliest start" value={d.logistics.earliest_start_date} />
            <CopyRow label="Relocate" value={RELOC[d.logistics.willing_to_relocate] || ''} />
            <CopyRow label="Travel %" value={d.logistics.willing_to_travel_pct ? `${d.logistics.willing_to_travel_pct}%` : ''} />
            <CopyRow label="Remote pref" value={REMOTE[d.logistics.remote_preference] || ''} />
          </Section>

          <Section title="Background">
            <CopyRow label="Highest degree" value={d.background.highest_degree} />
            <CopyRow label="University" value={d.background.university} />
            <CopyRow label="Graduated" value={d.background.graduation_year} />
            <CopyRow label="Total years exp" value={d.background.total_years_experience ? `${d.background.total_years_experience} years` : ''} />
          </Section>

          <Section title="Boilerplate Prose">
            <CopyRow label="Elevator pitch" value={d.boilerplate.elevator_pitch} />
            <CopyRow label="About yourself" value={d.boilerplate.tell_me_about_yourself} />
            <CopyRow label="Why looking" value={d.boilerplate.why_looking} />
            <CopyRow label="Strength" value={d.boilerplate.biggest_strength} />
            <CopyRow label="Weakness" value={d.boilerplate.biggest_weakness} />
          </Section>

          <div className="px-2 py-2 border-t border-slate-200 dark:border-slate-700 bg-slate-50/40 dark:bg-slate-800/40">
            <Link
              to="/settings"
              className="text-[11px] text-slate-500 dark:text-slate-400 hover:text-carrera-600 dark:hover:text-carrera-400 flex items-center gap-1"
            >
              <Settings size={11} /> Edit answers in Settings →
            </Link>
          </div>
        </>
      )}
    </div>
  )
}

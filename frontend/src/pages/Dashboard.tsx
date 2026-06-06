import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import {
  Briefcase, Bookmark, Send, Users, TrendingUp, Star, Radio, Sparkles, ArrowRight,
  Activity, Clock, FileText, RefreshCw, ExternalLink,
} from 'lucide-react'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, PieChart, Pie, Cell } from 'recharts'
import { formatDistanceToNow } from 'date-fns'
import clsx from 'clsx'
import { dashboardApi } from '../api/dashboard'
import { sourcesApi } from '../api/sources'
import { resumesApi } from '../api/resumes'
import type { DashboardStats } from '../types'
import BulkTailor from '../components/BulkTailor'
import { parseApiUtc } from '../lib/dateUtils'

const STAT_CARDS = (stats: DashboardStats) => [
  { label: 'New Today', value: stats.new_today, icon: TrendingUp, color: 'text-blue-500' },
  { label: 'Total Tracked', value: stats.total_tracked, icon: Briefcase, color: 'text-slate-500' },
  { label: 'Saved', value: stats.saved, icon: Bookmark, color: 'text-blue-600' },
  { label: 'Applied', value: stats.applied, icon: Send, color: 'text-violet-500' },
  { label: 'Interviewing', value: stats.interviewing, icon: Users, color: 'text-amber-500' },
  { label: 'Offers', value: stats.offers, icon: Star, color: 'text-emerald-500' },
  { label: 'Strong Matches', value: stats.strong_matches, icon: TrendingUp, color: 'text-emerald-600' },
  { label: 'Active Sources', value: stats.sources_active, icon: Radio, color: 'text-blue-500' },
]

const CATEGORY_COLORS: Record<string, string> = {
  strong_match: '#10b981',
  good_match: '#3b82f6',
  worth_a_look: '#f59e0b',
  reach: '#94a3b8',
}

export default function Dashboard() {
  const qc = useQueryClient()
  const { data: stats } = useQuery({ queryKey: ['stats'], queryFn: dashboardApi.stats })
  const { data: jobsOverTime } = useQuery({ queryKey: ['jobs-over-time'], queryFn: () => dashboardApi.jobsOverTime(30) })
  const { data: categories } = useQuery({ queryKey: ['categories'], queryFn: dashboardApi.categoryBreakdown })
  const { data: companies } = useQuery({ queryKey: ['companies'], queryFn: () => dashboardApi.topCompanies(8) })
  const { data: sources = [] } = useQuery({ queryKey: ['sources'], queryFn: sourcesApi.list })
  const { data: resumes = [] } = useQuery({ queryKey: ['resumes'], queryFn: resumesApi.list })
  const { data: recentActivity = [] } = useQuery({ queryKey: ['recent-activity'], queryFn: () => dashboardApi.recentActivity(10) })
  const { data: appliedWeek } = useQuery({ queryKey: ['applied-this-week'], queryFn: dashboardApi.appliedThisWeek })

  const fetchAllMutation = useMutation({
    mutationFn: sourcesApi.triggerFetchAll,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['stats'] })
      qc.invalidateQueries({ queryKey: ['sources'] })
      qc.invalidateQueries({ queryKey: ['jobs'] })
      qc.invalidateQueries({ queryKey: ['recent-activity'] })
      qc.invalidateQueries({ queryKey: ['jobs-over-time'] })
    },
  })
  const hasSources = sources.length > 0
  const hasEnabledSource = sources.some(s => s.enabled)
  const hasEverFetched = sources.some(s => !!s.last_fetched)
  const hasResume = resumes.length > 0
  const isEmpty = !!stats && stats.total_tracked === 0

  const pieData = categories
    ? Object.entries(categories).map(([k, v]) => ({ name: k.replace(/_/g, ' '), value: v, key: k }))
    : []

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-xl font-bold text-slate-900 dark:text-slate-100">Dashboard</h1>
          <p className="text-sm text-slate-500 dark:text-slate-400">Your job search overview</p>
        </div>
        <button
          onClick={() => fetchAllMutation.mutate()}
          disabled={fetchAllMutation.isPending || !hasEnabledSource}
          className="btn-primary text-xs"
          title={hasEnabledSource ? 'Run all enabled sources now' : 'Enable a source first'}
        >
          <RefreshCw size={13} className={clsx(fetchAllMutation.isPending && 'animate-spin')} />
          {fetchAllMutation.isPending ? 'Fetching…' : 'Fetch all sources'}
        </button>
      </div>

      {/* Getting Started panel — replaces thin empty state when nothing's been fetched yet */}
      {isEmpty && (
        <div className="card p-6 bg-gradient-to-br from-carrera-50 to-white dark:from-carrera-900/20 dark:to-slate-800 border-carrera-100 dark:border-carrera-900">
          <div className="flex items-start gap-3 mb-4">
            <Sparkles size={22} className="text-carrera-600 dark:text-carrera-400 shrink-0 mt-0.5" />
            <div>
              <h2 className="font-bold text-base text-slate-900 dark:text-slate-100">Welcome to Carrera</h2>
              <p className="text-xs text-slate-600 dark:text-slate-400 mt-0.5">
                Three steps to your first round of tailored applications.
              </p>
            </div>
          </div>

          <ol className="space-y-3">
            <OnboardStep
              done={hasSources && hasEnabledSource}
              number={1}
              title="Configure your sources"
              body={
                hasSources
                  ? `${sources.filter(s => s.enabled).length}/${sources.length} source(s) enabled. You can add more or tweak their search terms.`
                  : 'Sources are the job boards Carrera scrapes. LinkedIn, Gupy, Indeed, RemoteOK and more are pre-seeded.'
              }
              action={{ to: '/sources', label: hasSources ? 'Review sources' : 'Go to Sources' }}
            />
            <OnboardStep
              done={hasEverFetched}
              number={2}
              title="Run your first fetch"
              body={
                hasEverFetched
                  ? 'Fetches ran but no jobs stuck. Check the source configs — you may need to adjust search queries or locations.'
                  : 'Click "Fetch All" on the Sources page. It takes a few minutes; keep the tab open while it runs.'
              }
              action={{ to: '/sources', label: 'Open Sources' }}
            />
            <OnboardStep
              done={hasResume}
              number={3}
              title="Verify your base CV"
              body={
                hasResume
                  ? `${resumes.length} CV(s) ready: ${resumes.map(r => r.language.toUpperCase()).join(', ')}. Tweak bullets so tailoring has good material to work with.`
                  : 'Your CV is the source Carrera tailors from for each job. Seed data should have pre-populated it.'
              }
              action={{ to: '/resume', label: hasResume ? 'Edit CV' : 'Create CV' }}
            />
          </ol>

          <p className="text-[11px] text-slate-500 dark:text-slate-500 mt-4 ml-9">
            After your first fetch you'll see jobs in the <Link to="/jobs" className="text-carrera-600 dark:text-carrera-400 underline">Jobs</Link> page — open one and click <em>Tailor Resume</em> to generate an application.
          </p>
        </div>
      )}

      {/* Stat cards */}
      {stats && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          {STAT_CARDS(stats).map(card => (
            <div key={card.label} className="card p-4">
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs text-slate-500 dark:text-slate-400">{card.label}</span>
                <card.icon size={15} className={card.color} />
              </div>
              <p className="text-2xl font-bold text-slate-900 dark:text-slate-100">{card.value}</p>
            </div>
          ))}
        </div>
      )}

      {/* Charts row */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Jobs over time */}
        <div className="card p-4 lg:col-span-2">
          <h3 className="text-sm font-semibold text-slate-700 dark:text-slate-300 mb-4">Jobs Found (Last 30 Days)</h3>
          {jobsOverTime && jobsOverTime.length > 0 ? (
            <ResponsiveContainer width="100%" height={160}>
              <BarChart data={jobsOverTime} margin={{ top: 0, right: 0, left: -20, bottom: 0 }}>
                <XAxis
                  dataKey="date"
                  tick={{ fontSize: 10 }}
                  tickFormatter={d => d.slice(5)}
                  interval="preserveStartEnd"
                />
                <YAxis tick={{ fontSize: 10 }} allowDecimals={false} />
                <Tooltip
                  contentStyle={{ fontSize: 12 }}
                  formatter={(v: number) => [v, 'Jobs']}
                />
                <Bar dataKey="count" fill="#3b82f6" radius={[3, 3, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-40 flex items-center justify-center text-slate-400 dark:text-slate-600 text-sm">
              No data yet — run a scrape from Sources
            </div>
          )}
        </div>

        {/* Category pie */}
        <div className="card p-4">
          <h3 className="text-sm font-semibold text-slate-700 dark:text-slate-300 mb-4">By Category</h3>
          {pieData.length > 0 ? (
            <>
              <ResponsiveContainer width="100%" height={120}>
                <PieChart>
                  <Pie data={pieData} dataKey="value" outerRadius={50} innerRadius={25}>
                    {pieData.map(entry => (
                      <Cell key={entry.key} fill={CATEGORY_COLORS[entry.key] || '#94a3b8'} />
                    ))}
                  </Pie>
                  <Tooltip contentStyle={{ fontSize: 11 }} />
                </PieChart>
              </ResponsiveContainer>
              <div className="space-y-1 mt-2">
                {pieData.map(d => (
                  <div key={d.key} className="flex items-center justify-between text-xs">
                    <span className="flex items-center gap-1.5">
                      <span className="w-2 h-2 rounded-full" style={{ background: CATEGORY_COLORS[d.key] }} />
                      <span className="text-slate-600 dark:text-slate-400 capitalize">{d.name}</span>
                    </span>
                    <span className="font-medium text-slate-700 dark:text-slate-300">{d.value}</span>
                  </div>
                ))}
              </div>
            </>
          ) : (
            <div className="h-40 flex items-center justify-center text-slate-400 dark:text-slate-600 text-sm">
              No data yet
            </div>
          )}
        </div>
      </div>

      {/* Bulk tailor + Recent activity */}
      {!isEmpty && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <BulkTailor />
          <RecentActivityPanel activity={recentActivity} appliedWeek={appliedWeek} />
        </div>
      )}

      {/* Top companies */}
      {companies && companies.length > 0 && (
        <div className="card p-4">
          <h3 className="text-sm font-semibold text-slate-700 dark:text-slate-300 mb-4">Top Companies Hiring</h3>
          <div className="space-y-2">
            {companies.map(c => (
              <div key={c.company} className="flex items-center gap-3">
                <span className="text-xs text-slate-600 dark:text-slate-400 w-40 truncate">{c.company}</span>
                <div className="flex-1 bg-slate-100 dark:bg-slate-700 rounded-full h-1.5">
                  <div
                    className="bg-blue-500 h-1.5 rounded-full"
                    style={{ width: `${(c.count / (companies[0]?.count || 1)) * 100}%` }}
                  />
                </div>
                <span className="text-xs font-medium text-slate-500 dark:text-slate-400 w-5 text-right">{c.count}</span>
              </div>
            ))}
          </div>
        </div>
      )}

    </div>
  )
}

/* Mini sparkline of "applications submitted per day, last 7 days" + a feed
 * of every state change with a relative timestamp. The user wants to know
 * whether they're keeping pace and what they last did. */
function RecentActivityPanel({ activity, appliedWeek }: {
  activity: import('../api/dashboard').ActivityEntry[]
  appliedWeek?: { date: string; count: number }[]
}) {
  const totalThisWeek = (appliedWeek ?? []).reduce((s, d) => s + d.count, 0)

  return (
    <div className="card p-4 space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-slate-700 dark:text-slate-300 flex items-center gap-2">
          <Activity size={14} className="text-carrera-600 dark:text-carrera-400" />
          Recent activity
        </h3>
        <span className="text-[10px] text-slate-500 dark:text-slate-500">
          {totalThisWeek} applied this week
        </span>
      </div>

      {/* Trailing-7-day applied sparkline */}
      {appliedWeek && appliedWeek.length > 0 && (
        <div className="flex items-end gap-1 h-10">
          {appliedWeek.map(d => {
            const max = Math.max(1, ...appliedWeek.map(x => x.count))
            const h = Math.round((d.count / max) * 100)
            return (
              <div key={d.date} className="flex-1 flex flex-col items-center justify-end">
                <div
                  className={clsx(
                    'w-full rounded-sm transition-all',
                    d.count > 0 ? 'bg-carrera-500' : 'bg-slate-200 dark:bg-slate-700'
                  )}
                  style={{ height: `${Math.max(h, d.count > 0 ? 12 : 4)}%` }}
                  title={`${d.count} on ${d.date}`}
                />
                <span className="text-[9px] text-slate-400 mt-0.5">
                  {new Date(d.date + 'T00:00:00').toLocaleDateString(undefined, { weekday: 'narrow' })}
                </span>
              </div>
            )
          })}
        </div>
      )}

      {activity.length === 0 ? (
        <p className="text-xs text-slate-400 dark:text-slate-500 italic py-2">
          No activity yet — fetch sources, then apply.
        </p>
      ) : (
        <ul className="space-y-1.5 max-h-72 overflow-y-auto pr-1">
          {activity.map(a => (
            <li key={a.id} className="flex items-start gap-2 text-xs">
              <ActivityIcon action={a.action} />
              <div className="flex-1 min-w-0">
                <div className="text-slate-700 dark:text-slate-300 truncate">
                  <span className="font-medium">{actionLabel(a.action)}</span>
                  {' '}
                  <Link to="/jobs" className="text-carrera-600 dark:text-carrera-400 hover:underline">
                    {a.title}
                  </Link>
                  <span className="text-slate-400"> — {a.company}</span>
                </div>
                {a.details && (
                  <div className="text-[10px] text-slate-500 dark:text-slate-500 truncate">
                    {a.details}
                  </div>
                )}
              </div>
              <span className="text-[10px] text-slate-400 dark:text-slate-500 shrink-0">
                {formatDistanceToNow(parseApiUtc(a.timestamp), { addSuffix: true })}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

function ActivityIcon({ action }: { action: string }) {
  switch (action) {
    case 'discovered':
      return <Sparkles size={11} className="text-blue-500 shrink-0 mt-0.5" />
    case 'tailored':
      return <FileText size={11} className="text-violet-500 shrink-0 mt-0.5" />
    case 'applied':
      return <Send size={11} className="text-emerald-500 shrink-0 mt-0.5" />
    case 'status_change':
      return <ArrowRight size={11} className="text-amber-500 shrink-0 mt-0.5" />
    case 'note_added':
      return <ExternalLink size={11} className="text-slate-400 shrink-0 mt-0.5" />
    default:
      return <Clock size={11} className="text-slate-400 shrink-0 mt-0.5" />
  }
}

function actionLabel(action: string): string {
  return ({
    discovered: 'Discovered',
    tailored: 'Tailored',
    applied: 'Applied to',
    status_change: 'Status changed for',
    note_added: 'Note added to',
  } as Record<string, string>)[action] ?? action
}

function OnboardStep({ done, number, title, body, action }: {
  done: boolean
  number: number
  title: string
  body: string
  action: { to: string; label: string }
}) {
  return (
    <li className="flex items-start gap-3">
      <span
        className={
          done
            ? 'w-6 h-6 rounded-full bg-emerald-500 text-white flex items-center justify-center text-xs font-bold shrink-0 mt-0.5'
            : 'w-6 h-6 rounded-full bg-carrera-600 text-white flex items-center justify-center text-xs font-bold shrink-0 mt-0.5'
        }
      >
        {done ? '✓' : number}
      </span>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="font-semibold text-sm text-slate-800 dark:text-slate-200">{title}</span>
          {done && <span className="badge bg-emerald-50 dark:bg-emerald-900/30 text-emerald-600 text-[9px]">done</span>}
        </div>
        <p className="text-xs text-slate-600 dark:text-slate-400 mt-0.5">{body}</p>
        <Link
          to={action.to}
          className="inline-flex items-center gap-1 text-xs text-carrera-700 dark:text-carrera-400 hover:underline mt-1"
        >
          {action.label} <ArrowRight size={11} />
        </Link>
      </div>
    </li>
  )
}

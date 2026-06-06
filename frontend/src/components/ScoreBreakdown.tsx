import type { JobScore } from '../types'
import clsx from 'clsx'

const DIM_LABELS: Record<string, string> = {
  title: 'Title Match',
  location: 'Location',
  salary: 'Salary Range',
  skills: 'Skill Match',
  seniority: 'Seniority',
}

interface Props {
  scores: JobScore[]
  total: number
}

export default function ScoreBreakdown({ scores, total }: Props) {
  const totalPercent = Math.round(total * 100)

  const colorForScore = (s: number) => {
    if (s >= 0.75) return 'bg-emerald-500'
    if (s >= 0.5) return 'bg-blue-500'
    if (s >= 0.3) return 'bg-amber-500'
    return 'bg-red-400'
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <span className="text-sm font-semibold text-slate-700 dark:text-slate-300">Overall Score</span>
        <span className={clsx(
          'text-lg font-bold',
          totalPercent >= 75 ? 'text-emerald-600 dark:text-emerald-400' :
          totalPercent >= 55 ? 'text-blue-600 dark:text-blue-400' :
          totalPercent >= 35 ? 'text-amber-600 dark:text-amber-400' : 'text-slate-500'
        )}>
          {totalPercent}%
        </span>
      </div>

      <div className="w-full bg-slate-200 dark:bg-slate-700 rounded-full h-2">
        <div
          className={clsx('h-2 rounded-full transition-all', colorForScore(total))}
          style={{ width: `${totalPercent}%` }}
        />
      </div>

      <div className="space-y-2 pt-1">
        {scores.map(s => {
          const pct = Math.round(s.raw_score * 100)
          const label = DIM_LABELS[s.dimension] || s.dimension
          return (
            <div key={s.dimension}>
              <div className="flex items-center justify-between text-xs mb-0.5">
                <span className="text-slate-600 dark:text-slate-400">{label}</span>
                <span className="text-slate-500 dark:text-slate-400 font-mono">
                  {pct}% <span className="text-slate-400">× {Math.round(s.weight * 100)}%</span>
                </span>
              </div>
              <div className="w-full bg-slate-100 dark:bg-slate-700 rounded-full h-1.5">
                <div
                  className={clsx('h-1.5 rounded-full', colorForScore(s.raw_score))}
                  style={{ width: `${pct}%` }}
                />
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

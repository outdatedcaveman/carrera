import type { CVData } from '../types'

interface Props {
  cv: CVData
}

export default function ResumePreview({ cv }: Props) {
  const formatDate = (d: string | null | undefined) => {
    if (!d) return 'Present'
    const [year, month] = d.split('-')
    if (!month) return year
    const m = new Date(`${year}-${month}-01`).toLocaleString('default', { month: 'short' })
    return `${m} ${year}`
  }

  return (
    <div className="bg-white dark:bg-slate-900 rounded-lg border border-slate-200 dark:border-slate-700 p-6 text-sm font-sans text-slate-900 dark:text-slate-100 space-y-4 max-h-[60vh] overflow-y-auto">
      {/* Header */}
      <div className="border-b-2 border-blue-600 pb-3">
        <h1 className="text-xl font-bold text-slate-900 dark:text-slate-100">{cv.full_name}</h1>
        <div className="flex flex-wrap gap-x-4 gap-y-0.5 text-xs text-slate-500 dark:text-slate-400 mt-1">
          {cv.email && <span>{cv.email}</span>}
          {cv.location && <span>{cv.location}</span>}
          {cv.linkedin && <span>{cv.linkedin}</span>}
        </div>
      </div>

      {/* Summary */}
      {cv.summary && (
        <section>
          <h2 className="text-xs font-bold uppercase tracking-widest text-blue-600 dark:text-blue-400 mb-2">Summary</h2>
          <p className="text-xs text-slate-700 dark:text-slate-300 leading-relaxed">{cv.summary}</p>
        </section>
      )}

      {/* Experience */}
      {cv.experience?.length > 0 && (
        <section>
          <h2 className="text-xs font-bold uppercase tracking-widest text-blue-600 dark:text-blue-400 mb-2">Experience</h2>
          <div className="space-y-3">
            {cv.experience.map((exp, i) => (
              <div key={i}>
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <span className="text-xs font-semibold text-slate-800 dark:text-slate-200">{exp.title}</span>
                    <span className="text-xs text-slate-500 dark:text-slate-400"> · {exp.company}</span>
                  </div>
                  <span className="text-[10px] text-slate-400 whitespace-nowrap">
                    {formatDate(exp.start_date)} – {formatDate(exp.end_date)}
                  </span>
                </div>
                <ul className="mt-1 space-y-0.5">
                  {exp.bullets.slice(0, 4).map((b, bi) => (
                    <li key={bi} className="text-[11px] text-slate-600 dark:text-slate-400 flex gap-1.5">
                      <span className="shrink-0 text-blue-400 mt-0.5">•</span>
                      <span>{b}</span>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Education */}
      {cv.education?.length > 0 && (
        <section>
          <h2 className="text-xs font-bold uppercase tracking-widest text-blue-600 dark:text-blue-400 mb-2">Education</h2>
          <div className="space-y-2">
            {cv.education.map((edu, i) => (
              <div key={i} className="flex items-start justify-between gap-2">
                <div>
                  <span className="text-xs font-semibold text-slate-800 dark:text-slate-200">
                    {edu.degree} in {edu.field}
                  </span>
                  <p className="text-[11px] text-slate-500 dark:text-slate-400">{edu.institution}</p>
                </div>
                <span className="text-[10px] text-slate-400 whitespace-nowrap">
                  {edu.start_date} – {formatDate(edu.end_date)}
                </span>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Skills + Languages */}
      <div className="grid grid-cols-2 gap-4">
        {cv.skills?.length > 0 && (
          <section>
            <h2 className="text-xs font-bold uppercase tracking-widest text-blue-600 dark:text-blue-400 mb-1">Skills</h2>
            <p className="text-[11px] text-slate-600 dark:text-slate-400 leading-relaxed">
              {cv.skills.join(' · ')}
            </p>
          </section>
        )}
        {cv.languages?.length > 0 && (
          <section>
            <h2 className="text-xs font-bold uppercase tracking-widest text-blue-600 dark:text-blue-400 mb-1">Languages</h2>
            <div className="space-y-0.5">
              {cv.languages.map((l, i) => (
                <p key={i} className="text-[11px] text-slate-600 dark:text-slate-400">
                  <span className="font-medium">{l.language}</span>: {l.level}
                </p>
              ))}
            </div>
          </section>
        )}
      </div>
    </div>
  )
}

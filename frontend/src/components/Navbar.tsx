import { NavLink } from 'react-router-dom'
import { LayoutDashboard, Briefcase, Kanban, Radio, Settings, FileText, Moon, Sun } from 'lucide-react'
import clsx from 'clsx'

const NAV = [
  { to: '/dashboard', icon: LayoutDashboard, label: 'Dashboard' },
  { to: '/jobs', icon: Briefcase, label: 'Jobs' },
  { to: '/pipeline', icon: Kanban, label: 'Pipeline' },
  { to: '/resume', icon: FileText, label: 'Resume' },
  { to: '/sources', icon: Radio, label: 'Sources' },
  { to: '/settings', icon: Settings, label: 'Settings' },
]

interface Props {
  dark: boolean
  onToggleDark: () => void
}

function CarreraMark({ className = '' }: { className?: string }) {
  return (
    <svg viewBox="0 0 64 64" className={className} aria-hidden="true">
      <rect width="64" height="64" rx="14" fill="currentColor" />
      <path
        d="M46 22 C 41 16, 30 14, 24 20 C 18 26, 18 38, 24 44 C 30 50, 41 48, 46 42"
        stroke="#FFFFFF" strokeWidth="5.5" fill="none" strokeLinecap="round"
      />
      <path
        d="M34 32 L 46 32 M 40 26 L 46 32 L 40 38"
        stroke="#FBBF24" strokeWidth="4.5" fill="none" strokeLinecap="round" strokeLinejoin="round"
      />
    </svg>
  )
}

export default function Navbar({ dark, onToggleDark }: Props) {
  return (
    <header className="border-b border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 sticky top-0 z-40">
      <div className="container mx-auto px-4 max-w-7xl flex items-center gap-6 h-14">
        <NavLink to="/dashboard" className="flex items-center gap-2 shrink-0" title="Carrera — career in motion">
          <CarreraMark className="w-7 h-7 text-carrera-600 dark:text-carrera-500" />
          <span className="font-bold text-carrera-700 dark:text-carrera-400 text-lg tracking-tight">Carrera</span>
        </NavLink>

        <nav className="flex items-center gap-1 overflow-x-auto">
          {NAV.map(({ to, icon: Icon, label }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                clsx(
                  'flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium transition-colors whitespace-nowrap',
                  isActive
                    ? 'bg-blue-50 dark:bg-blue-900/30 text-blue-700 dark:text-blue-400'
                    : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-700'
                )
              }
            >
              <Icon size={15} />
              {label}
            </NavLink>
          ))}
        </nav>

        <button
          onClick={onToggleDark}
          className="ml-auto p-2 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-700 text-slate-500 dark:text-slate-400 transition-colors"
          title="Toggle theme"
        >
          {dark ? <Sun size={16} /> : <Moon size={16} />}
        </button>
      </div>
    </header>
  )
}

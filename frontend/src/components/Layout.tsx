import { BarChart3, Camera, Clock, Dumbbell, Menu } from 'lucide-react'
import type { ReactNode } from 'react'
import { Link, NavLink, useLocation } from 'react-router-dom'
import { useStore } from '../lib/store'

const NAV = [
  { to: '/', label: 'Check', icon: Camera, match: ['/', '/confirm', '/result', '/type'] },
  { to: '/history', label: 'History', icon: Clock, match: ['/history'] },
  { to: '/progress', label: 'Progress', icon: BarChart3, match: ['/progress'] },
  { to: '/practice', label: 'Practice', icon: Dumbbell, match: ['/practice', '/test-prep'] },
  { to: '/more', label: 'More', icon: Menu, match: ['/more', '/lessons', '/share', '/family', '/plans', '/account', '/privacy', '/how-it-works'] },
]

export function Logo({ className = '' }: { className?: string }) {
  return (
    <svg viewBox="0 0 64 64" className={className} aria-hidden>
      <rect width="64" height="64" rx="16" className="fill-ink" />
      <path d="M15 24h22M15 33h16M15 42h20" className="stroke-paper" strokeWidth="4" strokeLinecap="round" />
      <ellipse cx="29" cy="33" rx="20" ry="9" fill="none" className="stroke-pen" strokeWidth="3.5" transform="rotate(-6 29 33)" />
    </svg>
  )
}

export function Layout({ children }: { children: ReactNode }) {
  const { pathname } = useLocation()
  const { state } = useStore()
  const plus = state.plan !== 'free'
  const active = (match: string[]) => match.some((m) => (m === '/' ? pathname === '/' : pathname.startsWith(m)))

  return (
    <div className="min-h-dvh">
      <header className="sticky top-0 z-30 border-b border-line/60 bg-paper/85 backdrop-blur-md safe-top">
        <div className="mx-auto flex h-14 max-w-2xl items-center justify-between px-4">
          <Link to="/" className="flex items-center gap-2.5 font-semibold tracking-tight">
            <Logo className="size-8" />
            <span className="text-[15px]">Where Did I Go Wrong?</span>
          </Link>
          <Link
            to="/plans"
            className={`rounded-full px-2.5 py-1 text-xs font-semibold ${plus ? 'bg-accent-soft text-accent' : 'bg-surface-2 text-muted hover:text-ink'}`}
          >
            {plus ? (state.plan === 'family' ? 'Family' : 'Plus') : 'Free'}
          </Link>
        </div>
      </header>
      <main className="mx-auto max-w-2xl px-4 pb-32 pt-5">{children}</main>
      <nav className="fixed inset-x-0 bottom-0 z-30 border-t border-line/70 bg-surface/90 backdrop-blur-md safe-bottom" aria-label="Main">
        <div className="mx-auto grid h-16 max-w-2xl grid-cols-5">
          {NAV.map(({ to, label, icon: Icon, match }) => {
            const on = active(match)
            return (
              <NavLink key={to} to={to} className={`flex flex-col items-center justify-center gap-1 text-[11px] font-medium transition ${on ? 'text-ink' : 'text-faint hover:text-muted'}`}>
                <Icon className={`size-[22px] ${on ? 'stroke-[2.25]' : ''}`} aria-hidden />
                {label}
              </NavLink>
            )
          })}
        </div>
      </nav>
    </div>
  )
}

import { ChevronLeft, Loader2, Lock, X } from 'lucide-react'
import { createContext, useCallback, useContext, useEffect, useRef, useState, type ButtonHTMLAttributes, type ReactNode } from 'react'
import { Link, useNavigate } from 'react-router-dom'

type Variant = 'primary' | 'secondary' | 'ghost' | 'danger' | 'pen' | 'ok'
type Size = 'sm' | 'md' | 'lg'

const variants: Record<Variant, string> = {
  primary: 'bg-ink text-on-ink hover:bg-ink-soft shadow-sm',
  secondary: 'bg-surface text-ink border border-line hover:bg-surface-2',
  ghost: 'text-ink hover:bg-surface-2',
  danger: 'bg-surface text-pen border border-line hover:bg-pen-soft',
  pen: 'bg-pen text-white hover:opacity-90 shadow-sm',
  ok: 'bg-ok text-white hover:opacity-90 shadow-sm',
}
const sizes: Record<Size, string> = {
  sm: 'h-9 px-3 text-sm gap-1.5 rounded-xl',
  md: 'h-11 px-4 text-[15px] gap-2 rounded-2xl',
  lg: 'h-14 px-5 text-base gap-2.5 rounded-2xl',
}

export function Button({ variant = 'primary', size = 'md', loading = false, className = '', children, disabled, ...rest }:
  ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant; size?: Size; loading?: boolean }) {
  return (
    <button
      {...rest}
      disabled={disabled || loading}
      className={`inline-flex items-center justify-center font-medium transition active:scale-[0.98] disabled:opacity-50 disabled:pointer-events-none select-none ${variants[variant]} ${sizes[size]} ${className}`}
    >
      {loading && <Loader2 className="size-4 animate-spin" aria-hidden />}
      {children}
    </button>
  )
}

export function LinkButton({ to, variant = 'primary', size = 'md', className = '', children }:
  { to: string; variant?: Variant; size?: Size; className?: string; children: ReactNode }) {
  return (
    <Link to={to} className={`inline-flex items-center justify-center font-medium transition active:scale-[0.98] select-none ${variants[variant]} ${sizes[size]} ${className}`}>
      {children}
    </Link>
  )
}

export function Card({ children, className = '', ...rest }: { children: ReactNode; className?: string } & React.HTMLAttributes<HTMLDivElement>) {
  return <div {...rest} className={`rounded-3xl bg-surface border border-line ${className}`}>{children}</div>
}

export function Badge({ children, tone = 'neutral', className = '' }: { children: ReactNode; tone?: 'neutral' | 'ok' | 'pen' | 'warn' | 'num' | 'accent'; className?: string }) {
  const tones = {
    neutral: 'bg-surface-2 text-muted',
    ok: 'bg-ok-soft text-ok',
    pen: 'bg-pen-soft text-pen',
    warn: 'bg-warn-soft text-warn',
    num: 'bg-num-soft text-num',
    accent: 'bg-accent-soft text-accent',
  }
  return <span className={`inline-flex items-center gap-1 whitespace-nowrap rounded-full px-2 py-0.5 text-xs font-medium ${tones[tone]} ${className}`}>{children}</span>
}

export function Spinner({ label }: { label?: string }) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 py-10 text-muted" role="status">
      <Loader2 className="size-7 animate-spin" aria-hidden />
      {label && <p className="text-sm">{label}</p>}
    </div>
  )
}

export function PageHeader({ title, subtitle, back, right }: { title: string; subtitle?: ReactNode; back?: string | boolean; right?: ReactNode }) {
  const navigate = useNavigate()
  return (
    <div className="mb-5 flex items-start gap-2">
      {back && (
        <button
          onClick={() => (typeof back === 'string' ? navigate(back) : navigate(-1))}
          className="-ml-2 mt-0.5 grid size-9 shrink-0 place-items-center rounded-full hover:bg-surface-2"
          aria-label="Back"
        >
          <ChevronLeft className="size-5" />
        </button>
      )}
      <div className="min-w-0 flex-1">
        <h1 className="text-[26px] font-semibold leading-tight tracking-tight">{title}</h1>
        {subtitle && <p className="mt-1 text-[15px] text-muted">{subtitle}</p>}
      </div>
      {right}
    </div>
  )
}

export function Toggle({ checked, onChange, label, description, id }: { checked: boolean; onChange: (v: boolean) => void; label: ReactNode; description?: ReactNode; id: string }) {
  return (
    <label htmlFor={id} className="flex cursor-pointer items-start justify-between gap-4 py-3">
      <span className="min-w-0">
        <span className="block text-[15px] font-medium">{label}</span>
        {description && <span className="mt-0.5 block text-sm text-muted">{description}</span>}
      </span>
      <span className="relative mt-0.5 inline-flex shrink-0">
        <input id={id} type="checkbox" role="switch" className="peer sr-only" checked={checked} onChange={(e) => onChange(e.target.checked)} />
        <span className="h-7 w-12 rounded-full bg-line transition peer-checked:bg-ok peer-focus-visible:ring-2 peer-focus-visible:ring-accent" />
        <span className="absolute left-1 top-1 size-5 rounded-full bg-white shadow transition peer-checked:translate-x-5" />
      </span>
    </label>
  )
}

export function Field({ label, children, hint }: { label: string; children: ReactNode; hint?: ReactNode }) {
  return (
    <label className="block">
      <span className="mb-1.5 block text-sm font-medium text-muted">{label}</span>
      {children}
      {hint && <span className="mt-1 block text-xs text-faint">{hint}</span>}
    </label>
  )
}

export const inputClass = 'w-full h-12 rounded-2xl border border-line bg-surface px-4 text-[16px] text-ink placeholder:text-faint focus:outline-none focus:ring-2 focus:ring-accent/40 focus:border-accent'

export function Sheet({ open, onClose, title, children, wide = false }: { open: boolean; onClose: () => void; title: string; children: ReactNode; wide?: boolean }) {
  const ref = useRef<HTMLDivElement>(null)
  const closeRef = useRef(onClose)
  closeRef.current = onClose
  useEffect(() => {
    if (!open) return
    const prev = document.activeElement as HTMLElement | null
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') closeRef.current()
    }
    document.addEventListener('keydown', onKey)
    const t = setTimeout(() => ref.current?.querySelector<HTMLElement>('input, textarea, button')?.focus(), 50)
    const overflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => {
      document.removeEventListener('keydown', onKey)
      clearTimeout(t)
      document.body.style.overflow = overflow
      prev?.focus?.()
    }
  }, [open])
  if (!open) return null
  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center sm:items-center" role="dialog" aria-modal="true" aria-label={title}>
      <div className="absolute inset-0 bg-black/40 backdrop-blur-[2px]" onClick={onClose} />
      <div ref={ref} className={`sheet-in relative max-h-[92dvh] w-full overflow-y-auto rounded-t-3xl bg-surface p-5 pb-[max(2rem,env(safe-area-inset-bottom))] shadow-2xl sm:rounded-3xl ${wide ? 'sm:max-w-xl' : 'sm:max-w-md'}`}>
        <div className="mx-auto mb-3 h-1.5 w-10 rounded-full bg-line sm:hidden" />
        <div className="mb-4 flex items-center justify-between gap-3">
          <h2 className="text-lg font-semibold">{title}</h2>
          <button onClick={onClose} className="grid size-9 place-items-center rounded-full hover:bg-surface-2" aria-label="Close">
            <X className="size-5" />
          </button>
        </div>
        {children}
      </div>
    </div>
  )
}

export function LockCard({ title, children, compact = false }: { title: string; children?: ReactNode; compact?: boolean }) {
  return (
    <div className={`rounded-3xl border border-dashed border-line bg-surface-2/60 ${compact ? 'p-4' : 'p-5'}`}>
      <div className="flex items-start gap-3">
        <div className="grid size-9 shrink-0 place-items-center rounded-full bg-accent-soft text-accent">
          <Lock className="size-4" />
        </div>
        <div className="min-w-0 flex-1">
          <p className="font-medium">{title}</p>
          {children && <div className="mt-1 text-sm text-muted">{children}</div>}
          <LinkButton to="/plans" size="sm" className="mt-3">See Plus</LinkButton>
        </div>
      </div>
    </div>
  )
}

export function EmptyState({ icon, title, children, action }: { icon: ReactNode; title: string; children?: ReactNode; action?: ReactNode }) {
  return (
    <div className="flex flex-col items-center px-6 py-12 text-center">
      <div className="mb-4 grid size-14 place-items-center rounded-2xl bg-surface-2 text-muted">{icon}</div>
      <p className="font-semibold">{title}</p>
      {children && <p className="mt-1 max-w-xs text-sm text-muted">{children}</p>}
      {action && <div className="mt-5">{action}</div>}
    </div>
  )
}

export function Segmented<T extends string>({ value, options, onChange, label }: { value: T; options: { value: T; label: string }[]; onChange: (v: T) => void; label: string }) {
  return (
    <div role="radiogroup" aria-label={label} className="inline-flex rounded-2xl bg-surface-2 p-1">
      {options.map((o) => (
        <button
          key={o.value}
          role="radio"
          aria-checked={value === o.value}
          onClick={() => onChange(o.value)}
          className={`h-8 rounded-xl px-3 text-sm font-medium transition ${value === o.value ? 'bg-surface text-ink shadow-sm' : 'text-muted hover:text-ink'}`}
        >
          {o.label}
        </button>
      ))}
    </div>
  )
}

export function ErrorNote({ children }: { children: ReactNode }) {
  return <div role="alert" className="rounded-2xl bg-pen-soft px-4 py-3 text-sm text-pen">{children}</div>
}

// ----- toasts -----

interface Toast { id: number; text: string; tone: 'neutral' | 'ok' | 'pen' }
const ToastContext = createContext<(text: string, tone?: Toast['tone']) => void>(() => {})

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([])
  const push = useCallback((text: string, tone: Toast['tone'] = 'neutral') => {
    const id = Date.now() + Math.random()
    setToasts((t) => [...t.slice(-2), { id, text, tone }])
    setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), 3200)
  }, [])
  return (
    <ToastContext.Provider value={push}>
      {children}
      <div className="pointer-events-none fixed inset-x-0 top-3 z-[60] flex flex-col items-center gap-2 px-4 pt-[env(safe-area-inset-top)]" aria-live="polite">
        {toasts.map((t) => (
          <div key={t.id} className={`fade-up pointer-events-auto max-w-sm rounded-2xl px-4 py-2.5 text-sm font-medium shadow-lg ${t.tone === 'ok' ? 'bg-ok text-white' : t.tone === 'pen' ? 'bg-pen text-white' : 'bg-ink text-on-ink'}`}>
            {t.text}
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  )
}

export function useToast() {
  return useContext(ToastContext)
}

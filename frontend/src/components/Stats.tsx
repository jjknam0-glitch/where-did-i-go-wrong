// Small shared pieces for progress pages.

function upperFirst(s: string): string {
  return s ? s[0].toUpperCase() + s.slice(1) : s
}

export function Bars({ rows, label }: { rows: { key: string; count: number; pct: number }[]; label: (k: string) => string }) {
  const max = Math.max(1, ...rows.map((r) => r.count))
  return (
    <ul className="space-y-3">
      {rows.map((r) => (
        <li key={r.key}>
          <div className="mb-1 flex items-baseline justify-between gap-3 text-sm">
            <span className="truncate font-medium">{upperFirst(label(r.key))}</span>
            <span className="shrink-0 tabular-nums text-muted">{r.count} · {r.pct}%</span>
          </div>
          <div className="h-2.5 overflow-hidden rounded-full bg-surface-2">
            <div className="h-full rounded-full bg-pen" style={{ width: `${(r.count / max) * 100}%` }} />
          </div>
        </li>
      ))}
    </ul>
  )
}

export function Row({ icon, children }: { icon: React.ReactNode; children: React.ReactNode }) {
  return <li className="flex items-start gap-2.5"><span className="mt-0.5 text-muted">{icon}</span><span>{children}</span></li>
}


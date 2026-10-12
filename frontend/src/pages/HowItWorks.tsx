import { ArrowRight, Camera, CheckCircle2, Crop, Eye, ScanLine, Sigma, SplitSquareVertical, Wand2 } from 'lucide-react'
import { TierLegend } from '../components/StatusBits'
import { Card, PageHeader } from '../components/ui'

const PIPELINE = [
  { icon: Camera, title: 'Guided camera', text: 'Live checks for light, glare, framing, motion and blur; auto-capture when the photo is good.' },
  { icon: Crop, title: 'Clean up', text: 'Fix rotation, find the paper and warp it flat, even out lighting (CLAHE), remove notebook lines.' },
  { icon: SplitSquareVertical, title: 'Split into lines', text: 'A projection profile finds each line; fractions are merged; slanted writing falls back to component clustering.' },
  { icon: ScanLine, title: 'Read twice', text: 'Each line goes to a vision model alone, twice. The two readings are compared mathematically.' },
  { icon: Eye, title: 'You confirm', text: 'Unsure lines become a one-tap choice, so a misread never becomes a wrong verdict.' },
  { icon: Sigma, title: 'Math engine judges', text: 'SymPy compares each line to the one before: random exact-fraction tests plus a symbolic proof.' },
  { icon: Wand2, title: 'Classify & hint', text: 'Deterministic rules name the mistake (sign, one side only, distribution…) and build the hint ladder.' },
  { icon: CheckCircle2, title: 'Fix it yourself', text: 'Rewrite the step; the engine checks it and re-checks everything after it.' },
]

const TOPICS: [string, string, string][] = [
  ['Linear & quadratic equations', 'Same real solution set before and after', 'Verified'],
  ['Simplifying & factoring', 'A − B identically zero (numeric + simplify)', 'Verified'],
  ['Derivatives', 'Compute the derivative and compare', 'Verified'],
  ['Integrals', 'Differentiate the antiderivative, compare to the integrand', 'Verified'],
  ['Inequalities', 'Compare solution intervals — catches a missed flip', 'Verified'],
  ['Systems of equations', 'Each step must follow from the original system', 'Verified'],
  ['Trig identities', 'Random-value testing; symbolic when possible', 'Numeric / Verified'],
  ['Exponentials & logs', 'Equivalence on the valid domain', 'Verified'],
  ['Limits', 'SymPy limit of each side', 'Verified'],
]

const ROADMAP: [string, string][] = [
  ['Matrices & row reduction', 'Row space unchanged by each row operation'],
  ['Eigenvalues & eigenvectors', 'Check Av = λv directly'],
  ['Differential equations', 'Substitute the solution back'],
  ['Word problems & proofs', 'Clearly labeled “AI review — unverified”'],
  ['Teacher dashboard', 'A heatmap of which step a class misses most'],
  ['Check as you write', 'Prop the phone over the page; each new line is checked as it’s finished'],
]

export default function HowItWorks() {
  return (
    <div className="space-y-6">
      <PageHeader back title="How it works" subtitle="The AI reads the work. A math engine judges it." />

      <Card className="p-5">
        <ol className="space-y-4">
          {PIPELINE.map(({ icon: Icon, title, text }, i) => (
            <li key={title} className="flex gap-3">
              <div className="flex flex-col items-center">
                <div className={`grid size-9 place-items-center rounded-xl ${i === 3 ? 'bg-accent-soft text-accent' : 'bg-surface-2 text-ink'}`}><Icon className="size-4" /></div>
                {i < PIPELINE.length - 1 && <div className="mt-1 w-px flex-1 bg-line" />}
              </div>
              <div className="pb-1">
                <p className="font-medium">{title}{i === 3 && <span className="ml-2 rounded-full bg-accent-soft px-2 py-0.5 text-[11px] text-accent">the only AI step</span>}</p>
                <p className="text-sm text-muted">{text}</p>
              </div>
            </li>
          ))}
        </ol>
      </Card>

      <section>
        <h2 className="mb-2 text-lg font-semibold">The autocorrect trap</h2>
        <p className="text-[15px] leading-relaxed text-muted">
          Vision models tend to silently fix math mistakes, because they know what the right next step is. So each line is sent
          alone (the model can't see what the correct step would be), the prompt says to transcribe exactly what's written even
          if it's wrong, and the original problem is never shown during transcription.
        </p>
      </section>

      <section>
        <h2 className="mb-3 text-lg font-semibold">Every verdict shows how it was reached</h2>
        <Card className="p-5"><TierLegend /></Card>
        <p className="mt-3 text-sm text-muted">
          Telling a student that correct work is wrong is the worst failure, so the engine abstains whenever it can't be sure: when
          the two readings disagree, a line doesn't parse, the proof times out and the numbers are inconclusive, or the final answer
          contradicts the step-by-step result.
        </p>
      </section>

      <section>
        <h2 className="mb-3 text-lg font-semibold">Supported math</h2>
        <Card className="divide-y divide-line">
          {TOPICS.map(([t, how, tier]) => (
            <div key={t} className="flex items-start gap-3 px-4 py-3">
              <div className="min-w-0 flex-1"><p className="font-medium">{t}</p><p className="text-sm text-muted">{how}</p></div>
              <span className="shrink-0 rounded-full bg-ok-soft px-2 py-0.5 text-[11px] font-medium text-ok">{tier}</span>
            </div>
          ))}
        </Card>
        <p className="mt-3 text-sm text-muted">Why integrals work so well: two correct antiderivatives can look completely different (sin²x + C and −cos²x + C). Instead of integrating, the engine differentiates your answer — if it gives back the integrand, you're right, whatever form you used.</p>
      </section>

      <section>
        <h2 className="mb-3 text-lg font-semibold">Measured reliability</h2>
        <Card className="grid grid-cols-3 divide-x divide-line text-center">
          <div className="p-4"><p className="text-2xl font-semibold">0</p><p className="text-xs text-muted">false alarms on 300 random correct solutions</p></div>
          <div className="p-4"><p className="text-2xl font-semibold">99%</p><p className="text-xs text-muted">planted errors circled on the right line</p></div>
          <div className="p-4"><p className="text-2xl font-semibold">24/24</p><p className="text-xs text-muted">lines found in the sample photo set</p></div>
        </Card>
        <p className="mt-2 text-xs text-muted">Engine numbers come from the randomized test in the repository (the misses were steps that stayed mathematically valid). Real-handwriting transcription accuracy depends on the vision model and is measured per deployment.</p>
      </section>

      <section>
        <h2 className="mb-3 text-lg font-semibold">What's next</h2>
        <ul className="space-y-2">
          {ROADMAP.map(([t, d]) => (
            <li key={t} className="flex items-start gap-2 text-[15px]"><ArrowRight className="mt-1 size-4 shrink-0 text-faint" /><span><span className="font-medium">{t}</span> <span className="text-muted">— {d}</span></span></li>
          ))}
        </ul>
      </section>

      <section>
        <h2 className="mb-3 text-lg font-semibold">How it compares</h2>
        <Card className="overflow-x-auto">
          <table className="w-full min-w-[520px] text-left text-sm">
            <thead className="bg-surface-2/70 text-xs text-muted"><tr><th className="px-4 py-2"></th><th className="px-2 py-2">Answer apps</th><th className="px-2 py-2">AI chatbots</th><th className="px-2 py-2 text-ink">Where Did I Go Wrong?</th></tr></thead>
            <tbody className="divide-y divide-line">
              {[
                ['Reads your own work', 'Rarely', 'Sometimes', 'Always'],
                ['Finds the exact broken line', 'No', 'Unreliably', 'Yes, proven by the math engine'],
                ['Hands over the full answer', 'Yes', 'Yes', 'Only if asked'],
                ['Says when it’s unsure', 'No', 'Rarely', 'Always, with trust tiers'],
                ['Tracks mistake patterns', 'No', 'No', 'Yes'],
              ].map(([a, b, c, d]) => (
                <tr key={a}><td className="px-4 py-2.5 font-medium">{a}</td><td className="px-2 py-2.5 text-muted">{b}</td><td className="px-2 py-2.5 text-muted">{c}</td><td className="px-2 py-2.5 font-medium text-ok">{d}</td></tr>
              ))}
            </tbody>
          </table>
        </Card>
      </section>
    </div>
  )
}

import { BookOpen, ChevronRight, CreditCard, Download, Info, Share, Share2, Shield, SquarePlus, Timer, UserRound, Users } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { Logo } from '../components/Layout'
import { Button, Card, PageHeader, Sheet, useToast } from '../components/ui'
import { useStore } from '../lib/store'
import { useInstall } from '../lib/useInstall'

const ITEMS = [
  { to: '/lessons', icon: BookOpen, title: 'Why does this rule work?', desc: 'Concept mini-lessons' },
  { to: '/test-prep', icon: Timer, title: 'Test prep', desc: 'Top mistakes + a 10-minute drill' },
  { to: '/share', icon: Share2, title: 'Share with a parent or tutor', desc: 'Patterns and progress, never answers' },
  { to: '/family', icon: Users, title: 'Family view', desc: 'All your students in one place' },
  { to: '/plans', icon: CreditCard, title: 'Plans', desc: 'Free, Plus and Family' },
  { to: '/account', icon: UserRound, title: 'Account & settings', desc: 'Optional account, data, preferences' },
  { to: '/how-it-works', icon: Info, title: 'How it works', desc: 'The AI reads, the math engine judges' },
  { to: '/privacy', icon: Shield, title: 'Privacy & safety', desc: 'Photos are discarded by default' },
]

export default function More() {
  const { state } = useStore()
  const install = useInstall()
  const toast = useToast()
  const [howOpen, setHowOpen] = useState(false)
  return (
    <div>
      <PageHeader title="More" subtitle={state.account ? `Signed in as ${state.account.email}` : 'No account needed'} />
      {!install.installed && (
        <Card className="mb-5 flex items-center gap-4 p-4">
          <Logo className="size-12 shrink-0" />
          <div className="min-w-0 flex-1">
            <p className="font-medium">Install the app</p>
            <p className="text-sm text-muted">Opens full screen from your home screen, like any other app.</p>
          </div>
          <Button size="sm" onClick={async () => {
            if (install.canPrompt) {
              if (await install.prompt()) toast('Installed. Find it on your home screen.', 'ok')
            } else setHowOpen(true)
          }} data-testid="install-app"><Download className="size-4" /> Install</Button>
        </Card>
      )}
      <Sheet open={howOpen} onClose={() => setHowOpen(false)} title="Add it to your home screen">
        {install.ios ? (
          <ol className="space-y-4 text-[15px]">
            <li className="flex items-start gap-3"><span className="grid size-7 shrink-0 place-items-center rounded-full bg-surface-2 text-sm font-semibold">1</span><span>Open this page in <b>Safari</b>.</span></li>
            <li className="flex items-start gap-3"><span className="grid size-7 shrink-0 place-items-center rounded-full bg-surface-2 text-sm font-semibold">2</span><span>Tap the <b>Share</b> button <Share className="inline size-4 align-text-bottom" /> at the bottom of the screen.</span></li>
            <li className="flex items-start gap-3"><span className="grid size-7 shrink-0 place-items-center rounded-full bg-surface-2 text-sm font-semibold">3</span><span>Scroll down and tap <b>Add to Home Screen</b> <SquarePlus className="inline size-4 align-text-bottom" />, then <b>Add</b>.</span></li>
          </ol>
        ) : (
          <ol className="space-y-4 text-[15px]">
            <li className="flex items-start gap-3"><span className="grid size-7 shrink-0 place-items-center rounded-full bg-surface-2 text-sm font-semibold">1</span><span>Open this page in <b>Chrome</b> (Android) or <b>Chrome / Edge</b> (computer).</span></li>
            <li className="flex items-start gap-3"><span className="grid size-7 shrink-0 place-items-center rounded-full bg-surface-2 text-sm font-semibold">2</span><span>Open the browser menu <b>⋮</b>.</span></li>
            <li className="flex items-start gap-3"><span className="grid size-7 shrink-0 place-items-center rounded-full bg-surface-2 text-sm font-semibold">3</span><span>Tap <b>Install app</b> or <b>Add to Home screen</b>.</span></li>
          </ol>
        )}
        <p className="mt-5 text-sm text-muted">Your history is saved on each device. To carry it into the installed app, sign in under Account & settings first.</p>
      </Sheet>
      <ul className="divide-y divide-line overflow-hidden rounded-3xl border border-line bg-surface">
        {ITEMS.map(({ to, icon: Icon, title, desc }) => (
          <li key={to}>
            <Link to={to} className="flex items-center gap-3 px-4 py-3.5 transition hover:bg-surface-2">
              <Icon className="size-5 shrink-0 text-muted" />
              <span className="min-w-0 flex-1">
                <span className="block text-[15px] font-medium">{title}</span>
                <span className="block text-sm text-muted">{desc}</span>
              </span>
              <ChevronRight className="size-4 shrink-0 text-faint" />
            </Link>
          </li>
        ))}
      </ul>
      <p className="mt-6 text-center text-xs text-faint">Where Did I Go Wrong? · Built for Banana Hacks 2026</p>
    </div>
  )
}

import { BookOpen, ChevronRight, CreditCard, Info, Share2, Shield, Timer, UserRound, Users } from 'lucide-react'
import { Link } from 'react-router-dom'
import { PageHeader } from '../components/ui'
import { useStore } from '../lib/store'

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
  return (
    <div>
      <PageHeader title="More" subtitle={state.account ? `Signed in as ${state.account.email}` : 'No account needed'} />
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

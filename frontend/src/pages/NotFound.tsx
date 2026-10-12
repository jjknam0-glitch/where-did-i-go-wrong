import { Compass } from 'lucide-react'
import { EmptyState, LinkButton } from '../components/ui'

export default function NotFound() {
  return (
    <EmptyState icon={<Compass className="size-6" />} title="Page not found" action={<LinkButton to="/">Go home</LinkButton>}>
      That page doesn't exist.
    </EmptyState>
  )
}

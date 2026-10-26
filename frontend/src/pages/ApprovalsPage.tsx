import { useState } from 'react'
import { Alert } from '@/components/arc/alert/alert'
import { Button } from '@/components/arc/button/button'
import { EmptyState } from '@/components/arc/empty-state/empty-state'
import SegmentedControl from '@/components/arc/segmented-control/segmented-control'
import { Skeleton } from '@/components/arc/skeleton/skeleton'
import { ActionCard } from '@/components/chat/ActionCard'
import s from '@/components/chat/chat.module.css'
import { Page } from '@/components/layout/Page'
import { useActions } from '@/hooks/useActions'
import { go } from '@/hooks/useHash'

export default function ApprovalsPage() {
  const { data: actions, error } = useActions()
  const [filter, setFilter] = useState('pending')
  const pending = actions?.filter(a => a.status === 'pending') ?? []
  const list = filter === 'pending' ? pending : actions ?? []

  return (
    <Page
      title="Approvals"
      lead="What Syncra offered to do for you. Nothing runs until you approve it."
      action={
        <SegmentedControl
          label="Show"
          value={filter}
          onValueChange={setFilter}
          options={[{ value: 'pending', label: `Waiting (${pending.length})` }, { value: 'all', label: 'All' }]}
        />
      }
    >
      {error && <Alert tone="danger" title="Approvals didn't load">{error.message}</Alert>}
      {!actions && !error && <Skeleton lines={4} />}
      {actions && (list.length === 0
        ? <EmptyState
            title={filter === 'pending' ? 'Nothing waiting for you' : 'No actions yet'}
            description='Ask in a chat, for example "open a Jira ticket to add monitoring for the payment queue", and the card shows up here.'
            action={<Button variant="secondary" onClick={() => go('/')}>Start a chat</Button>}
          />
        : <div className={s.cards}>{list.map(a => <ActionCard key={a.id} card={a} chatLink />)}</div>)}
    </Page>
  )
}

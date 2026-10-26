import { ArrowUpRight } from 'lucide-react'
import type { Card } from '@/api/types'
import { Badge, type BadgeTone } from '@/components/arc/badge/badge'
import { Button } from '@/components/arc/button/button'
import { ExpandableText } from '@/components/arc/expandable-text/expandable-text'
import { BrandIcon } from '@/components/ToolIcon'
import { useDecideAction } from '@/hooks/useActions'
import { safeUrl } from '@/lib/format'
import s from './chat.module.css'

const STATUS: Record<Card['status'], [BadgeTone, string]> = {
  pending: ['info', 'Waiting for you'],
  approved: ['info', 'Running'],
  rejected: ['neutral', 'Rejected'],
  done: ['success', 'Created'],
  failed: ['danger', 'Failed'],
}

export function ActionCard({ card, chatLink }: { card: Card; chatLink?: boolean }) {
  const decide = useDecideAction()
  const busy = decide.isPending ? decide.variables.decision : null
  const [tone, label] = STATUS[card.status]
  const run = (decision: 'approve' | 'reject') => decide.mutate({ id: card.id, decision })

  return (
    <section className={s.card} aria-label={`Approval: ${card.payload.title}`}>
      <header className={s.cardHead}>
        <BrandIcon tool="jira" />
        <span className={s.cardKind}>Create a Jira ticket in <strong>{card.payload.project}</strong></span>
        <Badge tone={tone} size="sm">{label}</Badge>
      </header>
      <h3 className={s.cardTitle}>{card.payload.title}</h3>
      {card.payload.description && <ExpandableText lines={3} className={s.cardBody}>{card.payload.description}</ExpandableText>}

      {card.status === 'pending' && (
        <div className={s.cardActions}>
          <Button variant="ghost" size="sm" loading={busy === 'reject'} disabled={!!busy} onClick={() => run('reject')}>Reject</Button>
          <Button variant="primary" size="sm" loading={busy === 'approve'} disabled={!!busy} onClick={() => run('approve')}>Approve and create</Button>
        </div>
      )}
      {card.status === 'done' && card.result?.key && (
        <p className={s.cardResult}>
          Created <a href={safeUrl(card.result.link)} target="_blank" rel="noreferrer">{card.result.key}<ArrowUpRight size={14} strokeWidth={1.75} aria-hidden="true" /></a>
        </p>
      )}
      {card.status === 'failed' && card.result?.error && <p className={s.cardError}>{card.result.error}</p>}
      {decide.error && <p className={s.cardError} role="alert">{decide.error.message}</p>}
      {chatLink && card.session_id && <a className={s.cardLink} href={`#/chat/${card.session_id}`}>Open the chat</a>}
    </section>
  )
}

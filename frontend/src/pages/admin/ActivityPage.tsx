import { CircleAlert, RefreshCw, Timer } from 'lucide-react'
import { Alert } from '@/components/arc/alert/alert'
import { Button } from '@/components/arc/button/button'
import { EmptyState } from '@/components/arc/empty-state/empty-state'
import { Skeleton } from '@/components/arc/skeleton/skeleton'
import { Timeline, type TimelineEvent } from '@/components/arc/timeline/timeline'
import { Page } from '@/components/layout/Page'
import { useStatus } from '@/hooks/useAdmin'
import s from './admin.module.css'

const EVENT: Record<string, [string, TimelineEvent['tone']]> = {
  sync_failed: ['Sync failed', 'danger'],
  learn_failed: ['Learning run failed', 'danger'],
  model_error: ['Model error', 'danger'],
  slow_answer: ['Slow answer', 'neutral'],
}

const METRICS = [
  ['processed', 'Learned', 'Items searchable in answers'],
  ['new', 'Waiting', 'Fetched, learned on the next run'],
  ['noise', 'Noise', 'Dropped as small talk or bots'],
  ['failed', 'Failed', "Couldn't be processed"],
] as const

export default function ActivityPage() {
  const { data, error, refetch, dataUpdatedAt } = useStatus()

  const items = data?.items ?? {}
  const events: TimelineEvent[] = (data?.events ?? []).map((e, i) => ({
    id: `${e.created_at}-${i}`,
    at: e.created_at,
    title: EVENT[e.kind]?.[0] ?? e.kind,
    tone: EVENT[e.kind]?.[1] ?? 'neutral',
    icon: e.kind === 'slow_answer' ? <Timer size={14} strokeWidth={1.75} /> : <CircleAlert size={14} strokeWidth={1.75} />,
    detail: <p className={s.eventText}>{e.message}</p>,
  }))
  const failing = data?.sources.filter(src => src.last_error) ?? []

  return (
    <Page
      title="Activity"
      lead="What Syncra has learned, and what went wrong lately: failed syncs and learning runs, model errors and slow answers."
      action={<Button variant="secondary" onClick={() => refetch()}><RefreshCw size={16} strokeWidth={1.75} aria-hidden="true" />Refresh</Button>}
    >
      {error && <Alert tone="danger" title="Activity didn't load">{error.message}</Alert>}
      {!data && !error && <Skeleton lines={5} />}
      {data && (
        <div className={s.stack}>
          <dl className={s.metrics}>
            {METRICS.map(([key, label, context]) => (
              <div key={key} className={s.metric}>
                <dt>{label}</dt>
                <dd>{(items[key] ?? 0).toLocaleString()}</dd>
                <p>{context}</p>
              </div>
            ))}
          </dl>

          {failing.length > 0 && (
            <Alert tone="danger" title={`${failing.length} ${failing.length === 1 ? 'source is' : 'sources are'} failing to sync`}>
              {failing.map(f => f.name).join(', ')}. See Sources for the errors.
            </Alert>
          )}

          <section aria-labelledby="events">
            <h2 id="events" className={s.sectionTitle}>Recent problems</h2>
            {events.length === 0
              ? <EmptyState title="Nothing went wrong lately" description="Failed syncs, model errors and slow answers show up here." />
              : <Timeline events={events} now={dataUpdatedAt} label="Recent problems" timeZone={Intl.DateTimeFormat().resolvedOptions().timeZone} />}
          </section>
        </div>
      )}
    </Page>
  )
}

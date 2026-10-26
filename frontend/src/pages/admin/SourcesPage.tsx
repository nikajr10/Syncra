import { useState, type FormEvent } from 'react'
import { Plus } from 'lucide-react'
import type { SourceView, Tool } from '@/api/types'
import { Alert } from '@/components/arc/alert/alert'
import { Badge } from '@/components/arc/badge/badge'
import { Button } from '@/components/arc/button/button'
import { Dialog, DialogContent } from '@/components/arc/dialog/dialog'
import { EmptyState } from '@/components/arc/empty-state/empty-state'
import { ExpandableText } from '@/components/arc/expandable-text/expandable-text'
import { Input } from '@/components/arc/input/input'
import { Select } from '@/components/arc/select/select'
import { Skeleton } from '@/components/arc/skeleton/skeleton'
import { Switch } from '@/components/arc/switch/switch'
import { Page } from '@/components/layout/Page'
import { BrandIcon } from '@/components/ToolIcon'
import { useAddSource, useSources, useSyncSource, useToggleSource } from '@/hooks/useAdmin'
import { TOOL_NAME, TOOLS, timeAgo, toolOptions } from '@/lib/format'
import s from './admin.module.css'

const ID_HINT: Record<Tool, string> = {
  github: 'owner/repo, e.g. acme/payments',
  jira: 'Project key, e.g. PAY',
  slack: 'Channel ID, e.g. C0123ABCD',
}

export default function SourcesPage() {
  const { data, error } = useSources()
  const [adding, setAdding] = useState(false)

  return (
    <Page
      title="Sources"
      action={<Button variant="primary" onClick={() => setAdding(true)}><Plus size={16} strokeWidth={1.75} aria-hidden="true" />Add source</Button>}
    >
      {error && <Alert tone="danger" title="Failed to load sources">{error.message}</Alert>}
      {!data && !error && <Skeleton lines={4} />}
      {data && (
        <>
          <ul className={s.tools} aria-label="Tool credentials">
            {TOOLS.map(t => (
              <li key={t} className={s.tool}>
                <BrandIcon tool={t} size={20} />
                <span className={s.toolName}>{TOOL_NAME[t]}</span>
                {data.tools[t]
                  ? <Badge tone="success" size="sm">Connected</Badge>
                  : <Badge tone="warning" size="sm">Not configured</Badge>}
              </li>
            ))}
          </ul>

          {data.sources.length === 0
            ? <EmptyState title="No sources" description="Add a GitHub repo, Jira project or Slack channel." action={<Button variant="secondary" onClick={() => setAdding(true)}>Add source</Button>} />
            : (
              <ul className={s.list} aria-label="Sources">
                {data.sources.map(src => <SourceRow key={src.id} source={src} />)}
              </ul>
            )}
        </>
      )}
      <AddSource open={adding} onOpenChange={setAdding} />
    </Page>
  )
}

function SourceRow({ source }: { source: SourceView }) {
  const toggle = useToggleSource()
  const sync = useSyncSource()
  const [startedFrom, setStartedFrom] = useState<string | null | undefined>(undefined) // last_synced_at when "Sync now" was pressed
  const syncing = startedFrom !== undefined && startedFrom === source.last_synced_at && !source.last_error
  const error = toggle.error ?? sync.error

  return (
    <li className={s.row}>
      <BrandIcon tool={source.kind} size={20} />
      <div className={s.rowMain}>
        <div className={s.rowTitle}>
          <span className={s.name}>{source.name}</span>
          {source.name !== source.external_id && <span className={s.muted}>{source.external_id}</span>}
        </div>
        <div className={s.rowMeta}>
          {syncing
            ? <span>Syncing…</span>
            : source.last_error
            ? <Badge tone="danger" size="sm">Last sync failed</Badge>
            : !source.enabled
              ? <Badge size="sm">Paused</Badge>
              : <span>{source.last_synced_at ? `Synced ${timeAgo(source.last_synced_at)}` : 'Not synced yet'}</span>}
          <span>{source.items.toLocaleString()} items</span>
          <span>{source.members} {source.members === 1 ? 'member' : 'members'}</span>
        </div>
        {source.last_error && <ExpandableText lines={2} className={s.error}>{source.last_error}</ExpandableText>}
        {error && <p className={s.error} role="alert">{error.message}</p>}
      </div>
      <div className={s.rowActions}>
        <Switch label="Sync" checked={source.enabled} onCheckedChange={enabled => toggle.mutate({ source, enabled })} />
        <Button
          variant="secondary"
          size="sm"
          loading={sync.isPending}
          disabled={!source.enabled || syncing}
          onClick={() => sync.mutate(source.id, { onSuccess: () => setStartedFrom(source.last_synced_at) })}
        >
          Sync now
        </Button>
      </div>
    </li>
  )
}

function AddSource({ open, onOpenChange }: { open: boolean; onOpenChange: (o: boolean) => void }) {
  const [kind, setKind] = useState<Tool>('github')
  const add = useAddSource()

  function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault()
    const form = new FormData(e.currentTarget)
    add.mutate(
      { kind, externalId: String(form.get('external_id')).trim(), name: String(form.get('name')).trim() },
      { onSuccess: () => onOpenChange(false) },
    )
  }

  return (
    <Dialog open={open} onOpenChange={o => { onOpenChange(o); if (!o) add.reset() }}>
      <DialogContent title="Add source">
        <form className={s.form} onSubmit={submit}>
          <Select label="Tool" options={toolOptions} value={kind} onValueChange={v => setKind(v as Tool)} />
          <Input label={kind === 'github' ? 'Repository' : kind === 'jira' ? 'Project key' : 'Channel ID'} description={ID_HINT[kind]} name="external_id" required autoComplete="off" spellCheck={false} />
          <Input label="Name" description="Optional" name="name" autoComplete="off" />
          <Alert tone="danger" title="Failed to add source" open={add.isError}>{add.error?.message}</Alert>
          <div className={s.formActions}>
            <Button type="button" variant="ghost" onClick={() => onOpenChange(false)}>Cancel</Button>
            <Button type="submit" variant="primary" loading={add.isPending}>Add source</Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  )
}

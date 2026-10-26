import { useCallback, useEffect, useState, type FormEvent, type ReactNode } from 'react'
import { CircleAlert, Plus, RefreshCw, Timer } from 'lucide-react'
import { api, type SourceView, type Tool, type UserView } from '@/api'
import { Alert } from '@/components/arc/alert/alert'
import { Avatar } from '@/components/arc/avatar/avatar'
import { Badge } from '@/components/arc/badge/badge'
import { Button } from '@/components/arc/button/button'
import { Dialog, DialogContent } from '@/components/arc/dialog/dialog'
import { EmptyState } from '@/components/arc/empty-state/empty-state'
import { ExpandableText } from '@/components/arc/expandable-text/expandable-text'
import { Input } from '@/components/arc/input/input'
import { MetricCard } from '@/components/arc/metric-card/metric-card'
import { Select } from '@/components/arc/select/select'
import { Skeleton } from '@/components/arc/skeleton/skeleton'
import { Switch } from '@/components/arc/switch/switch'
import { TextShimmer } from '@/components/arc/text-shimmer/text-shimmer'
import { Timeline, type TimelineEvent } from '@/components/arc/timeline/timeline'
import { BrandIcon, TOOL_NAME, timeAgo } from './ui'
import page from './page.module.css'
import s from './Admin.module.css'

const TOOLS: Tool[] = ['github', 'jira', 'slack']
const toolOptions = TOOLS.map(t => ({ value: t, label: TOOL_NAME[t] }))

/** Load once, and again every `every` ms while the page is open. */
function useLoad<T>(load: () => Promise<T>, every?: number) {
  const [data, setData] = useState<T | null>(null)
  const [error, setError] = useState('')
  const reload = useCallback(() => load().then(d => { setData(d); setError('') }, e => setError(e.message)), [load])
  useEffect(() => {
    reload()
    if (!every) return
    const timer = setInterval(reload, every)
    return () => clearInterval(timer)
  }, [reload, every])
  return { data, error, reload, setData }
}

function Page({ title, lead, action, children }: { title: string; lead: string; action?: ReactNode; children: ReactNode }) {
  return (
    <div className={page.page}>
      <header className={page.pageHead}>
        <div>
          <h1 className={page.pageTitle}>{title}</h1>
          <p className={page.pageLead}>{lead}</p>
        </div>
        {action}
      </header>
      <div className={page.section}>{children}</div>
    </div>
  )
}

// --- Sources -----------------------------------------------------------------------------------

const ID_HINT: Record<Tool, string> = {
  github: 'The repo as owner/name, like acme/payments',
  jira: 'The project key, like PAY',
  slack: 'The channel id, like C0123ABCD (channel details, at the bottom)',
}

export function SourcesPage() {
  const { data, error, reload, setData } = useLoad(api.sources, 10_000) // a sync in progress shows up without a refresh
  const [adding, setAdding] = useState(false)

  const replace = (view: SourceView) =>
    setData(d => d && { ...d, sources: d.sources.map(x => (x.id === view.id ? view : x)) })

  return (
    <Page
      title="Sources"
      lead="The repos, projects and channels Syncra learns from. A new source syncs with the next learning run, or now."
      action={<Button variant="primary" onClick={() => setAdding(true)}><Plus size={16} strokeWidth={1.75} aria-hidden="true" />Add source</Button>}
    >
      {error && <Alert tone="danger" title="Sources didn't load">{error}</Alert>}
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
                  : <Badge tone="warning" size="sm">No token in backend/.env</Badge>}
              </li>
            ))}
          </ul>

          {data.sources.length === 0
            ? <EmptyState title="No sources yet" description="Add a GitHub repo, Jira project or Slack channel and Syncra starts learning from it." action={<Button variant="secondary" onClick={() => setAdding(true)}>Add source</Button>} />
            : (
              <ul className={s.list} aria-label="Sources">
                {data.sources.map(src => <SourceRow key={src.id} source={src} onChange={replace} />)}
              </ul>
            )}
        </>
      )}
      <AddSource open={adding} onOpenChange={setAdding} onAdded={reload} />
    </Page>
  )
}

function SourceRow({ source, onChange }: { source: SourceView; onChange: (s: SourceView) => void }) {
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [startedFrom, setStartedFrom] = useState<string | null | undefined>(undefined) // last_synced_at when "Sync now" was pressed
  const syncing = startedFrom !== undefined && startedFrom === source.last_synced_at && !source.last_error
  const syncNow = async () => {
    setBusy(true)
    setError('')
    try { onChange(await api.syncSource(source.id)); setStartedFrom(source.last_synced_at) } catch (e) { setError((e as Error).message) }
    setBusy(false)
  }
  const toggle = async (enabled: boolean) => {
    onChange({ ...source, enabled })
    try { onChange(await api.setSource(source.id, enabled)) } catch (e) { onChange(source); setError((e as Error).message) }
  }

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
            ? <TextShimmer>Syncing now</TextShimmer>
            : source.last_error
            ? <Badge tone="danger" size="sm">Last sync failed</Badge>
            : !source.enabled
              ? <Badge size="sm">Paused</Badge>
              : <span>{source.last_synced_at ? `Synced ${timeAgo(source.last_synced_at)}` : 'Not synced yet'}</span>}
          <span>{source.items.toLocaleString()} items</span>
          <span>{source.members} {source.members === 1 ? 'person' : 'people'} can see it</span>
        </div>
        {source.last_error && <ExpandableText lines={2} className={s.error}>{source.last_error}</ExpandableText>}
        {error && <p className={s.error} role="alert">{error}</p>}
      </div>
      <div className={s.rowActions}>
        <Switch label="Sync" checked={source.enabled} onCheckedChange={toggle} />
        <Button variant="secondary" size="sm" loading={busy} disabled={!source.enabled || syncing} onClick={syncNow}>Sync now</Button>
      </div>
    </li>
  )
}

function AddSource({ open, onOpenChange, onAdded }: { open: boolean; onOpenChange: (o: boolean) => void; onAdded: () => void }) {
  const [kind, setKind] = useState<Tool>('github')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault()
    const form = new FormData(e.currentTarget)
    setBusy(true)
    setError('')
    try {
      await api.addSource(kind, String(form.get('external_id')).trim(), String(form.get('name')).trim())
      onAdded()
      onOpenChange(false)
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={o => { onOpenChange(o); if (!o) setError('') }}>
      <DialogContent title="Add a source" description="Syncra reads it with the credentials in backend/.env and only shows it to people who can see it there.">
        <form className={s.form} onSubmit={submit}>
          <Select label="Tool" options={toolOptions} value={kind} onValueChange={v => setKind(v as Tool)} />
          <Input label={kind === 'github' ? 'Repository' : kind === 'jira' ? 'Project key' : 'Channel id'} description={ID_HINT[kind]} name="external_id" required autoComplete="off" spellCheck={false} />
          <Input label="Name" description="Optional. Shown in answers instead of the id." name="name" autoComplete="off" />
          <Alert tone="danger" title="Couldn't add it" open={!!error}>{error}</Alert>
          <div className={s.formActions}>
            <Button type="button" variant="ghost" onClick={() => onOpenChange(false)}>Cancel</Button>
            <Button type="submit" variant="primary" loading={busy}>Add source</Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  )
}

// --- People ------------------------------------------------------------------------------------

const ACCOUNT_HINT: Record<Tool, string> = {
  github: 'Their GitHub login, like alice-chen',
  jira: 'Their Jira accountId, from their Jira profile URL',
  slack: 'Their Slack member id, like U0123ABCD (profile, more, copy member id)',
}

export function PeoplePage() {
  const { data, error, reload } = useLoad(api.users)
  const [linking, setLinking] = useState<UserView | null>(null)

  return (
    <Page title="People" lead="Linked accounts decide what each person can search: they only see the repos, projects and channels their accounts can see.">
      {error && <Alert tone="danger" title="People didn't load">{error}</Alert>}
      {!data && !error && <Skeleton lines={4} avatar />}
      {data?.length === 0 && <EmptyState title="No people yet" description="Create users with make add-user in backend/." />}
      {data && data.length > 0 && (
        <ul className={s.list} aria-label="People">
          {data.map(u => (
            <li key={u.username} className={s.row}>
              <Avatar name={u.display_name || u.username} size="md" />
              <div className={s.rowMain}>
                <div className={s.rowTitle}>
                  <span className={s.name}>{u.display_name || u.username}</span>
                  <span className={s.muted}>@{u.username}</span>
                  {u.is_admin && <Badge tone="info" size="sm">Admin</Badge>}
                </div>
                <div className={s.accounts}>
                  {u.accounts.length === 0 && <span className={s.warn}>No linked accounts, so they can't search anything yet</span>}
                  {u.accounts.map(a => (
                    <span key={`${a.tool}:${a.id}`} className={s.account} title={a.display_name ?? undefined}>
                      <BrandIcon tool={a.tool} size={14} />{a.id}
                    </span>
                  ))}
                </div>
              </div>
              <div className={s.rowActions}>
                <Button variant="secondary" size="sm" onClick={() => setLinking(u)}>Link account</Button>
              </div>
            </li>
          ))}
        </ul>
      )}
      <LinkAccount user={linking} onClose={() => setLinking(null)} onLinked={reload} />
    </Page>
  )
}

function LinkAccount({ user, onClose, onLinked }: { user: UserView | null; onClose: () => void; onLinked: () => void }) {
  const [tool, setTool] = useState<Tool>('github')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault()
    if (!user) return
    const form = new FormData(e.currentTarget)
    setBusy(true)
    setError('')
    try {
      await api.linkAccount(user.username, tool, String(form.get('account_id')).trim(), String(form.get('display_name')).trim())
      onLinked()
      onClose()
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <Dialog open={!!user} onOpenChange={o => { if (!o) { onClose(); setError('') } }}>
      <DialogContent title={`Link an account to ${user?.display_name || user?.username || ''}`} description="An account can belong to one person only. Linking the same account again renames it.">
        <form className={s.form} onSubmit={submit}>
          <Select label="Tool" options={toolOptions} value={tool} onValueChange={v => setTool(v as Tool)} />
          <Input label="Account id" description={ACCOUNT_HINT[tool]} name="account_id" required autoComplete="off" spellCheck={false} />
          <Input label="Display name" description="Optional. How the account shows up in answers." name="display_name" autoComplete="off" />
          <Alert tone="danger" title="Couldn't link it" open={!!error}>{error}</Alert>
          <div className={s.formActions}>
            <Button type="button" variant="ghost" onClick={onClose}>Cancel</Button>
            <Button type="submit" variant="primary" loading={busy}>Link account</Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  )
}

// --- Activity ----------------------------------------------------------------------------------

const EVENT: Record<string, [string, TimelineEvent['tone']]> = {
  sync_failed: ['Sync failed', 'danger'],
  learn_failed: ['Learning run failed', 'danger'],
  model_error: ['Model error', 'danger'],
  slow_answer: ['Slow answer', 'neutral'],
}

const loadStatus = () => api.status().then(status => ({ status, now: Date.now() })) // the Timeline's "now"

export function ActivityPage() {
  const { data: loaded, error, reload } = useLoad(loadStatus, 30_000)
  const data = loaded?.status
  const now = loaded?.now ?? 0

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
      action={<Button variant="secondary" onClick={reload}><RefreshCw size={16} strokeWidth={1.75} aria-hidden="true" />Refresh</Button>}
    >
      {error && <Alert tone="danger" title="Activity didn't load">{error}</Alert>}
      {!data && !error && <Skeleton lines={5} />}
      {data && (
        <div className={s.stack}>
          <div className={s.metrics}>
            <MetricCard label="Learned" value={items.processed ?? 0} context="Items searchable in answers" />
            <MetricCard label="Waiting" value={items.new ?? 0} context="Fetched, learned on the next run" />
            <MetricCard label="Noise" value={items.noise ?? 0} context="Dropped as small talk or bots" />
            <MetricCard label="Failed" value={items.failed ?? 0} context="Couldn't be processed" />
          </div>

          {failing.length > 0 && (
            <Alert tone="danger" title={`${failing.length} ${failing.length === 1 ? 'source is' : 'sources are'} failing to sync`}>
              {failing.map(f => f.name).join(', ')}. See Sources for the errors.
            </Alert>
          )}

          <section aria-labelledby="events">
            <h2 id="events" className={s.sectionTitle}>Recent problems</h2>
            {events.length === 0
              ? <EmptyState title="Nothing went wrong lately" description="Failed syncs, model errors and slow answers show up here." />
              : <Timeline events={events} now={now} label="Recent problems" timeZone={Intl.DateTimeFormat().resolvedOptions().timeZone} />}
          </section>
        </div>
      )}
    </Page>
  )
}

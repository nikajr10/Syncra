import { Fragment, useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from 'react'
import { ArrowUp, ArrowUpRight, ShieldAlert } from 'lucide-react'
import { api, streamMessage, type Card, type Chat, type Confidence, type Message, type Reply, type Source } from '@/api'
import { ActionButton } from '@/components/arc/action-button/action-button'
import { Alert } from '@/components/arc/alert/alert'
import { Badge, type BadgeTone } from '@/components/arc/badge/badge'
import { Button } from '@/components/arc/button/button'
import { CopyButton } from '@/components/arc/copy-button/copy-button'
import { EmptyState } from '@/components/arc/empty-state/empty-state'
import { ExpandableText } from '@/components/arc/expandable-text/expandable-text'
import { HoverCard } from '@/components/arc/hover-card/hover-card'
import SegmentedControl from '@/components/arc/segmented-control/segmented-control'
import { Skeleton } from '@/components/arc/skeleton/skeleton'
import { TextShimmer } from '@/components/arc/text-shimmer/text-shimmer'
import { BrandIcon, TOOL_NAME, TypeIcon, timeAgo, toolOf, typeName } from './ui'
import s from './Chat.module.css'
import page from './page.module.css'

/** A message on screen: a saved one, or the reply being streamed into place. */
interface Turn extends Partial<Omit<Message, 'role'>> {
  role: Message['role']
  content: string
  streaming?: boolean
  path?: Reply['path']
  followUps?: string[]
  actionId?: number
  error?: string
}

// Questions the demo company (backend/demo) can answer; harmless elsewhere.
const STARTERS = [
  'Why did we pick RabbitMQ instead of Kafka?',
  'Why are refund retries capped at 3?',
  'What does PAY-131 say?',
  'Open a Jira ticket to add monitoring for the payment queue',
]

interface ChatViewProps {
  chatId: number | null
  name: string
  actions: Card[]
  onChatCreated: (chat: Chat) => void
  onReplied: () => void
  onCardChange: (card: Card) => void
}

export function ChatView({ chatId, name, actions, onChatCreated, onReplied, onCardChange }: ChatViewProps) {
  const [turns, setTurns] = useState<Turn[] | null>(chatId ? null : [])
  const [busy, setBusy] = useState(false)
  const [loadError, setLoadError] = useState('')
  const created = useRef<number | null>(null) // the chat this view just created: its turns are already on screen
  const scroller = useRef<HTMLDivElement>(null)
  const stuck = useRef(true) // follow new text only while the reader is at the bottom
  const viewing = useRef(chatId) // a reply streaming into another chat stays there

  useEffect(() => {
    viewing.current = chatId
    setLoadError('')
    if (chatId === null) { setTurns([]); return }
    if (chatId === created.current) { created.current = null; return }
    let live = true
    setTurns(null)
    api.messages(chatId).then(
      list => { if (live) { setTurns(list); stuck.current = true } },
      err => { if (live) setLoadError(err.message) },
    )
    return () => { live = false }
  }, [chatId])

  useEffect(() => {
    const el = scroller.current
    if (el && stuck.current) el.scrollTop = el.scrollHeight
  }, [turns])

  const patchLast = (chat: number | null, patch: Partial<Turn> | ((t: Turn) => Partial<Turn>)) => {
    if (viewing.current !== chat) return
    setTurns(list => list && list.map((t, i) => (i === list.length - 1 ? { ...t, ...(typeof patch === 'function' ? patch(t) : patch) } : t)))
  }

  async function send(text: string) {
    text = text.trim()
    if (!text || busy) return
    setBusy(true)
    stuck.current = true
    setTurns(list => [...(list ?? []), { role: 'user', content: text }, { role: 'assistant', content: '', streaming: true }])
    let id = chatId
    try {
      if (id === null) {
        const chat = await api.newChat(text.length > 80 ? `${text.slice(0, 77)}…` : text)
        created.current = viewing.current = id = chat.id
        onChatCreated(chat)
      }
      const reply = await streamMessage(id, text, piece => patchLast(id, t => ({ content: t.content + piece })))
      patchLast(id, {
        content: reply.reply, streaming: false, path: reply.path, sources: reply.sources,
        confidence: reply.confidence, followUps: reply.follow_ups, actionId: reply.action?.id,
      })
      onReplied()
    } catch (err) {
      patchLast(id, { streaming: false, error: err instanceof Error ? err.message : 'Something went wrong' })
    } finally {
      setBusy(false)
    }
  }

  // Saved action cards carry no message id: a card belongs to the reply saved in the same transaction.
  const cardFor = (turn: Turn) => {
    if (turn.actionId) return actions.find(a => a.id === turn.actionId)
    if (turn.role !== 'assistant' || !turn.created_at) return undefined
    const at = new Date(turn.created_at).getTime()
    return actions.find(a => a.session_id === chatId && Math.abs(new Date(a.created_at).getTime() - at) < 2000)
  }

  const empty = turns?.length === 0
  const last = turns?.[turns.length - 1]

  return (
    <div className={s.chat}>
      <div
        ref={scroller}
        className={s.scroll}
        onScroll={e => { const el = e.currentTarget; stuck.current = el.scrollHeight - el.scrollTop - el.clientHeight < 48 }}
      >
        <div className={s.column}>
          {loadError && <Alert tone="danger" title="This chat didn't load">{loadError}</Alert>}
          {!turns && !loadError && <div className={s.loading}><Skeleton lines={2} /><Skeleton lines={4} /></div>}
          {empty && (
            <div className={s.welcome}>
              <h1 className={s.hello}>What do you want to know, {name}?</h1>
              <p className={s.helloLead}>Ask about decisions, code, tickets or conversations. Answers cite the GitHub, Jira and Slack items they come from.</p>
              <div className={s.starters}>
                {STARTERS.map(q => (
                  <button key={q} type="button" className={s.starter} onClick={() => send(q)}>
                    <span>{q}</span><ArrowUpRight size={16} strokeWidth={1.75} aria-hidden="true" />
                  </button>
                ))}
              </div>
            </div>
          )}
          {turns?.map((t, i) => {
            const card = cardFor(t)
            return (
              <Fragment key={i}>
                {t.role === 'user'
                  ? <div className={s.user}><p>{t.content}</p></div>
                  : <Answer turn={t} onAsk={send} canAsk={!busy && t === last} retry={t.error && i > 0 ? () => send(turns[i - 1].content) : undefined} />}
                {card && <ActionCard card={card} onChange={onCardChange} />}
              </Fragment>
            )
          })}
        </div>
      </div>
      <Composer busy={busy} onSend={send} />
    </div>
  )
}

const CONFIDENCE: Record<Confidence, [BadgeTone, string]> = {
  high: ['success', 'High confidence'],
  medium: ['warning', 'Medium confidence'],
  low: ['danger', 'Low confidence'],
}

function Answer({ turn, onAsk, canAsk, retry }: { turn: Turn; onAsk: (q: string) => void; canAsk: boolean; retry?: () => void }) {
  const sources = turn.sources ?? []
  const [allSources, setAllSources] = useState(false)

  if (turn.error) return (
    <Alert tone="danger" title="No answer this time">
      {turn.error}
      {retry && <div className={s.retry}><Button size="sm" variant="secondary" onClick={retry}>Ask again</Button></div>}
    </Alert>
  )
  if (turn.path === 'blocked') return (
    <div className={s.blocked} role="status">
      <ShieldAlert size={20} strokeWidth={1.75} aria-hidden="true" />
      <p>{turn.content}</p>
    </div>
  )
  if (turn.streaming && !turn.content) return (
    <div className={s.answer} aria-live="polite"><TextShimmer>Searching your team's memory</TextShimmer></div>
  )

  const shown = allSources ? sources : sources.slice(0, 3)
  return (
    <article className={s.answer} aria-busy={turn.streaming || undefined}>
      <div className={s.prose} data-streaming={turn.streaming || undefined}>
        <Cited text={turn.content} sources={sources} />
      </div>

      {!turn.streaming && (turn.confidence || sources.length > 0) && (
        <div className={s.meta}>
          {turn.confidence && <Badge tone={CONFIDENCE[turn.confidence][0]} size="sm">{CONFIDENCE[turn.confidence][1]}</Badge>}
          {sources.length > 0 && <span className={s.metaText}>{sources.length} {sources.length === 1 ? 'source' : 'sources'}</span>}
          <span className={s.copy}><CopyButton value={turn.content.replace(/\s?\[E\d+\]/g, '')} label="Copy answer" iconOnly variant="plain" /></span>
        </div>
      )}

      {!turn.streaming && sources.length > 0 && (
        <ol className={s.sources} aria-label="Sources">
          {shown.map(src => (
            <li key={src.label} id={`src-${src.label}`}>
              <SourceRow source={src} />
            </li>
          ))}
          {sources.length > 3 && (
            <li>
              <button type="button" className={s.more} onClick={() => setAllSources(v => !v)}>
                {allSources ? 'Show fewer sources' : `Show all ${sources.length} sources`}
              </button>
            </li>
          )}
        </ol>
      )}

      {canAsk && !turn.streaming && (turn.followUps?.length ?? 0) > 0 && (
        <div className={s.followUps} aria-label="Follow-up questions">
          {turn.followUps!.map(q => (
            <button key={q} type="button" className={s.followUp} onClick={() => onAsk(q)}>{q}</button>
          ))}
        </div>
      )}
    </article>
  )
}

/** The answer text with each [E#] turned into a numbered chip that previews its source. */
function Cited({ text, sources }: { text: string; sources: Source[] }) {
  return text.split(/(\[E\d+\])/g).map((part, i) => {
    const label = /^\[(E\d+)\]$/.exec(part)?.[1]
    if (!label) return <Fragment key={i}>{part}</Fragment>
    const source = sources.find(src => src.label === label)
    const n = label.slice(1)
    const link = safe(source?.link)
    if (!source) return <span key={i} className={s.cite} aria-label={`Source ${n}`}>{n}</span>
    return (
      <HoverCard key={i} side="top" content={<SourcePreview source={source} />}>
        <a className={s.cite} href={link ?? `#src-${label}`} target={link ? '_blank' : undefined} rel="noreferrer" aria-label={`Source ${n}: ${source.title ?? typeName(source.type)}`}>{n}</a>
      </HoverCard>
    )
  })
}

/** Source and ticket links come from the tools' data: only http(s) becomes a link. */
const safe = (url: string | null | undefined) => (url && /^https?:\/\//i.test(url) ? url : undefined)

function sourceMeta(source: Source) {
  const author = source.author?.replace(/\s*\((github|jira|slack):[^)]*\)$/, '') // "Alice Chen (github:alice-chen)"
  return [typeName(source.type), author, source.date && timeAgo(source.date)].filter(Boolean).join(' · ')
}

function SourcePreview({ source }: { source: Source }) {
  const tool = toolOf(source.type, source.link)
  return (
    <div className={s.preview}>
      <div className={s.previewHead}>
        {tool ? <BrandIcon tool={tool} /> : <TypeIcon type={source.type} />}
        <span className={s.metaText}>{sourceMeta(source)}</span>
      </div>
      <p className={s.previewTitle}>{source.title ?? typeName(source.type)}</p>
      <p className={s.previewExcerpt}>{source.excerpt}</p>
      {source.link && tool && <span className={s.metaText}>Opens in {TOOL_NAME[tool]}</span>}
    </div>
  )
}

function SourceRow({ source }: { source: Source }) {
  const tool = toolOf(source.type, source.link)
  const body = (
    <>
      <span className={s.sourceNum}>{source.label.slice(1)}</span>
      <span className={s.sourceIcon}><TypeIcon type={source.type} /></span>
      <span className={s.sourceText}>
        <span className={s.sourceTitle}>{source.title ?? typeName(source.type)}</span>
        <span className={s.metaText}>{sourceMeta(source)}</span>
      </span>
      {tool && <BrandIcon tool={tool} size={14} />}
    </>
  )
  const link = safe(source.link)
  return link
    ? <a className={s.source} href={link} target="_blank" rel="noreferrer">{body}</a>
    : <div className={s.source}>{body}</div>
}

function Composer({ busy, onSend }: { busy: boolean; onSend: (text: string) => void }) {
  const [text, setText] = useState('')
  const box = useRef<HTMLTextAreaElement>(null)

  useEffect(() => {
    const el = box.current
    if (el) { el.style.height = 'auto'; el.style.height = `${el.scrollHeight}px` }
  }, [text])

  const submit = (e?: FormEvent) => {
    e?.preventDefault()
    if (!text.trim() || busy) return
    onSend(text)
    setText('')
  }
  const onKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) submit(e)
  }

  return (
    <form className={s.composerWrap} onSubmit={submit}>
      <div className={s.composer}>
        <label htmlFor="message" className="sr-only">Message</label>
        <textarea
          id="message"
          ref={box}
          rows={1}
          maxLength={4000}
          value={text}
          onChange={e => setText(e.target.value)}
          onKeyDown={onKeyDown}
          placeholder="Ask about your team's work"
          autoFocus={matchMedia('(pointer: fine)').matches} // no keyboard popping up on phones
        />
        <button type="submit" className={s.send} disabled={!text.trim() || busy} aria-label="Send">
          <ArrowUp size={18} strokeWidth={2} aria-hidden="true" />
        </button>
      </div>
      <p className={s.hint}>Enter to send, Shift and Enter for a new line. Check the sources before you act on an answer.</p>
    </form>
  )
}

const STATUS: Record<Card['status'], [BadgeTone, string]> = {
  pending: ['info', 'Waiting for you'],
  approved: ['info', 'Running'],
  rejected: ['neutral', 'Rejected'],
  done: ['success', 'Created'],
  failed: ['danger', 'Failed'],
}

export function ActionCard({ card, onChange, chatLink }: { card: Card; onChange: (card: Card) => void; chatLink?: boolean }) {
  const [rejecting, setRejecting] = useState(false)
  const [error, setError] = useState('')
  const [tone, label] = STATUS[card.status]

  const run = async (call: () => Promise<Card>) => {
    setError('')
    try { onChange(await call()) } catch (err) { setError(err instanceof Error ? err.message : 'That did not work'); throw err }
  }

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
          <Button variant="ghost" size="sm" loading={rejecting} onClick={() => { setRejecting(true); run(() => api.reject(card.id)).catch(() => setRejecting(false)) }}>Reject</Button>
          <ActionButton label="Approve and create" pendingLabel="Creating ticket" successLabel="Created" onAction={() => run(() => api.approve(card.id))} onActionError={() => {}} />
        </div>
      )}
      {card.status === 'done' && card.result?.key && (
        <p className={s.cardResult}>
          Created <a href={safe(card.result.link)} target="_blank" rel="noreferrer">{card.result.key}<ArrowUpRight size={14} strokeWidth={1.75} aria-hidden="true" /></a>
        </p>
      )}
      {card.status === 'failed' && card.result?.error && <p className={s.cardError}>{card.result.error}</p>}
      {error && <p className={s.cardError} role="alert">{error}</p>}
      {chatLink && card.session_id && <a className={s.cardLink} href={`#/chat/${card.session_id}`}>Open the chat</a>}
    </section>
  )
}

export function Approvals({ actions, onChange }: { actions: Card[]; onChange: (card: Card) => void }) {
  const [filter, setFilter] = useState('pending')
  const pending = actions.filter(a => a.status === 'pending')
  const list = filter === 'pending' ? pending : actions

  return (
    <div className={page.page}>
      <header className={page.pageHead}>
        <div>
          <h1 className={page.pageTitle}>Approvals</h1>
          <p className={page.pageLead}>What Syncra offered to do for you. Nothing runs until you approve it.</p>
        </div>
        <SegmentedControl
          label="Show"
          value={filter}
          onValueChange={setFilter}
          options={[{ value: 'pending', label: `Waiting (${pending.length})` }, { value: 'all', label: 'All' }]}
        />
      </header>
      {list.length === 0
        ? <EmptyState
            title={filter === 'pending' ? 'Nothing waiting for you' : 'No actions yet'}
            description='Ask in a chat, for example "open a Jira ticket to add monitoring for the payment queue", and the card shows up here.'
            action={<Button variant="secondary" onClick={() => { location.hash = '/' }}>Start a chat</Button>}
          />
        : <div className={s.cards}>{list.map(a => <ActionCard key={a.id} card={a} onChange={onChange} chatLink />)}</div>}
    </div>
  )
}

import { Fragment, useState } from 'react'
import { ShieldAlert } from 'lucide-react'
import type { Confidence, Source } from '@/api/types'
import { Alert } from '@/components/arc/alert/alert'
import { Badge, type BadgeTone } from '@/components/arc/badge/badge'
import { Button } from '@/components/arc/button/button'
import { CopyButton } from '@/components/arc/copy-button/copy-button'
import { HoverCard } from '@/components/arc/hover-card/hover-card'
import { BrandIcon, TypeIcon } from '@/components/ToolIcon'
import type { Turn } from '@/hooks/useChats'
import { TOOL_NAME, safeUrl, timeAgo, toolOf, typeName } from '@/lib/format'
import s from './chat.module.css'

const CONFIDENCE: Record<Confidence, [BadgeTone, string]> = {
  high: ['success', 'High confidence'],
  medium: ['warning', 'Medium confidence'],
  low: ['danger', 'Low confidence'],
}

export function Answer({ turn, onAsk, canAsk, retry }: { turn: Turn; onAsk: (q: string) => void; canAsk: boolean; retry?: () => void }) {
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
    <div className={s.answer} aria-live="polite"><p className={s.metaText}>Searching your team's memory…</p></div>
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
    const link = safeUrl(source?.link)
    if (!source) return <span key={i} className={s.cite} aria-label={`Source ${n}`}>{n}</span>
    return (
      <HoverCard key={i} side="top" content={<SourcePreview source={source} />}>
        <a className={s.cite} href={link ?? `#src-${label}`} target={link ? '_blank' : undefined} rel="noreferrer" aria-label={`Source ${n}: ${source.title ?? typeName(source.type)}`}>{n}</a>
      </HoverCard>
    )
  })
}

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
  const link = safeUrl(source.link)
  return link
    ? <a className={s.source} href={link} target="_blank" rel="noreferrer">{body}</a>
    : <div className={s.source}>{body}</div>
}

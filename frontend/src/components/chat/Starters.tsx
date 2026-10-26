import { ArrowUpRight, PenLine } from 'lucide-react'
import type { Suggestions } from '@/api/types'
import s from './chat.module.css'

/** Questions from the newest decisions and tickets this user may see (GET /chat/suggestions). */
export function Starters({ suggested, onAsk, onDraft }: { suggested: Suggestions | null; onAsk: (q: string) => void; onDraft: (text: string) => void }) {
  if (!suggested) return (
    <div className={s.starters} aria-busy="true" aria-label="Loading suggestions">
      {[0, 1, 2, 3].map(i => <div key={i} className={s.starterSkeleton} />)}
    </div>
  )
  const { questions, ticket_project: project } = suggested
  if (!questions.length && !project) return (
    <p className={s.noSuggestions}>
      No suggestions yet.
    </p>
  )
  return (
    <div className={s.starters}>
      {questions.map(q => (
        <button key={q} type="button" className={s.starter} onClick={() => onAsk(q)}>
          <span>{q}</span><ArrowUpRight size={16} strokeWidth={1.75} aria-hidden="true" />
        </button>
      ))}
      {project && (
        <button type="button" className={s.starter} onClick={() => onDraft(`Open a Jira ticket in ${project} to `)}>
          <span>Create a Jira ticket in {project}…</span>
          <PenLine size={16} strokeWidth={1.75} aria-hidden="true" />
        </button>
      )}
    </div>
  )
}

import { Fragment, useEffect, useRef, useState } from 'react'
import { Alert } from '@/components/arc/alert/alert'
import { Skeleton } from '@/components/arc/skeleton/skeleton'
import { ActionCard } from '@/components/chat/ActionCard'
import { Answer } from '@/components/chat/Answer'
import { Composer } from '@/components/chat/Composer'
import { Starters } from '@/components/chat/Starters'
import s from '@/components/chat/chat.module.css'
import { useActions } from '@/hooks/useActions'
import { useMessages, useSendMessage, useSuggestions, type Turn } from '@/hooks/useChats'

const NO_SUGGESTIONS = { questions: [], ticket_project: null }

export default function ChatPage({ chatId, name }: { chatId: number | null; name: string }) {
  const { data: turns, error } = useMessages(chatId)
  const { data: actions = [] } = useActions()
  const empty = turns?.length === 0
  const suggestions = useSuggestions(empty)
  const sendMessage = useSendMessage()
  const [draft, setDraft] = useState({ text: '', n: 0 }) // a new n remounts the composer with this text
  const scroller = useRef<HTMLDivElement>(null)
  const stuck = useRef(true) // follow new text only while the reader is at the bottom
  const busy = turns?.some(t => t.streaming) ?? false

  useEffect(() => { stuck.current = true }, [chatId])
  useEffect(() => {
    const el = scroller.current
    if (el && stuck.current) el.scrollTop = el.scrollHeight
  }, [turns])

  const send = (text: string) => {
    text = text.trim()
    if (!text || busy) return
    stuck.current = true
    sendMessage(chatId, text)
  }

  // Saved action cards carry no message id: a card belongs to the reply saved in the same transaction.
  const cardFor = (turn: Turn) => {
    if (turn.actionId) return actions.find(a => a.id === turn.actionId)
    if (turn.role !== 'assistant' || !turn.created_at) return undefined
    const at = new Date(turn.created_at).getTime()
    return actions.find(a => a.session_id === chatId && Math.abs(new Date(a.created_at).getTime() - at) < 2000)
  }

  const last = turns?.[turns.length - 1]

  return (
    <div className={s.chat}>
      <div
        ref={scroller}
        className={s.scroll}
        onScroll={e => { const el = e.currentTarget; stuck.current = el.scrollHeight - el.scrollTop - el.clientHeight < 48 }}
      >
        <div className={s.column}>
          {error && <Alert tone="danger" title="This chat didn't load">{error.message}</Alert>}
          {!turns && !error && <div className={s.loading}><Skeleton lines={2} /><Skeleton lines={4} /></div>}
          {empty && (
            <div className={s.welcome}>
              <h1 className={s.hello}>What do you want to know, {name}?</h1>
              <p className={s.helloLead}>Ask about decisions, code, tickets or conversations. Answers cite the GitHub, Jira and Slack items they come from.</p>
              <Starters
                suggested={suggestions.data ?? (suggestions.isError ? NO_SUGGESTIONS : null)}
                onAsk={send}
                onDraft={text => setDraft(d => ({ text, n: d.n + 1 }))}
              />
            </div>
          )}
          {turns?.map((t, i) => {
            const card = cardFor(t)
            return (
              <Fragment key={i}>
                {t.role === 'user'
                  ? <div className={s.user}><p>{t.content}</p></div>
                  : <Answer turn={t} onAsk={send} canAsk={!busy && t === last} retry={t.error && i > 0 ? () => send(turns[i - 1].content) : undefined} />}
                {card && <ActionCard card={card} />}
              </Fragment>
            )
          })}
        </div>
      </div>
      <Composer key={draft.n} busy={busy} onSend={send} initial={draft.text} />
    </div>
  )
}

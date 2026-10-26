import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from 'react'
import { ArrowUp } from 'lucide-react'
import s from './chat.module.css'

export function Composer({ busy, onSend, initial }: { busy: boolean; onSend: (text: string) => void; initial: string }) {
  const [text, setText] = useState(initial)
  const box = useRef<HTMLTextAreaElement>(null)

  useEffect(() => {
    const el = box.current
    if (initial && el) { el.focus(); el.setSelectionRange(initial.length, initial.length) } // a drafted request: finish typing it
  }, [initial])

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

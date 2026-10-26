import type { ReactNode } from 'react'
import s from './Page.module.css'

/** A page beside the chat: a title, a one-line lead, an optional action and the content. */
export function Page({ title, lead, action, children }: { title: string; lead: string; action?: ReactNode; children: ReactNode }) {
  return (
    <div className={s.page}>
      <header className={s.pageHead}>
        <div>
          <h1 className={s.pageTitle}>{title}</h1>
          <p className={s.pageLead}>{lead}</p>
        </div>
        {action}
      </header>
      <div className={s.section}>{children}</div>
    </div>
  )
}

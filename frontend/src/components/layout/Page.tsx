import type { ReactNode } from 'react'
import s from './Page.module.css'

/** A page beside the chat: a title, an optional action and the content. */
export function Page({ title, action, children }: { title: string; action?: ReactNode; children: ReactNode }) {
  return (
    <div className={s.page}>
      <header className={s.pageHead}>
        <h1 className={s.pageTitle}>{title}</h1>
        {action}
      </header>
      <div className={s.section}>{children}</div>
    </div>
  )
}

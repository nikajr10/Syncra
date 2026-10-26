import { Suspense, useState, type ReactNode } from 'react'
import { Activity, CheckSquare, LogOut, Menu, Plus, Unplug, Users, X } from 'lucide-react'
import type { Me } from '@/api/types'
import { Badge } from '@/components/arc/badge/badge'
import { useActions } from '@/hooks/useActions'
import { useLogout } from '@/hooks/useAuth'
import { useChats } from '@/hooks/useChats'
import s from './Shell.module.css'

const PAGES = [
  { path: '/approvals', label: 'Approvals', icon: CheckSquare, admin: false },
  { path: '/sources', label: 'Sources', icon: Unplug, admin: true },
  { path: '/people', label: 'People', icon: Users, admin: true },
  { path: '/activity', label: 'Activity', icon: Activity, admin: true },
]

/** The sidebar (chats, pages, account) and the mobile top bar around the current page. */
export function Shell({ me, hash, chatId, children }: { me: Me; hash: string; chatId: number | null; children: ReactNode }) {
  const { data: chats = [] } = useChats()
  const { data: actions = [] } = useActions()
  const logout = useLogout()
  const [navOpen, setNavOpen] = useState(false)

  const pending = actions.filter(a => a.status === 'pending').length
  const pages = PAGES.filter(p => !p.admin || me.is_admin)

  return (
    <div className={s.shell} data-nav-open={navOpen || undefined}>
      <aside className={s.sidebar} aria-label="Chats and pages" onClick={e => { if ((e.target as Element).closest('a')) setNavOpen(false) }}>
        <div className={s.brandRow}>
          <a href="#/" className={s.brand}><img src="/favicon.svg" alt="" width={24} height={24} />Syncra</a>
          <button type="button" className={s.iconButton} onClick={() => setNavOpen(false)} aria-label="Close menu" data-mobile-only><X size={20} strokeWidth={1.75} /></button>
        </div>

        <a href="#/" className={s.newChat}><Plus size={16} strokeWidth={1.75} aria-hidden="true" />New chat</a>

        <nav className={s.chatList} aria-label="Chats">
          {chats.length === 0 && <p className={s.muted}>No chats yet</p>}
          {chats.map(c => (
            <a key={c.id} href={`#/chat/${c.id}`} className={s.navItem} aria-current={chatId === c.id ? 'page' : undefined}>
              <span className={s.navLabel}>{c.title || 'Untitled chat'}</span>
            </a>
          ))}
        </nav>

        <nav className={s.pages} aria-label="Pages">
          {pages.map(p => (
            <a key={p.path} href={`#${p.path}`} className={s.navItem} aria-current={hash === p.path ? 'page' : undefined}>
              <p.icon size={16} strokeWidth={1.75} aria-hidden="true" />
              <span className={s.navLabel}>{p.label}</span>
              {p.path === '/approvals' && pending > 0 && <Badge tone="info" size="sm">{pending}<span className="sr-only"> waiting</span></Badge>}
            </a>
          ))}
        </nav>

        <div className={s.account}>
          <span className={s.accountName}>
            {me.display_name || me.username}
            <small>@{me.username}{me.is_admin && ' · Admin'}</small>
          </span>
          <button type="button" className={s.iconButton} onClick={() => logout.mutate()} disabled={logout.isPending} aria-label="Sign out" title="Sign out"><LogOut size={18} strokeWidth={1.75} /></button>
        </div>
      </aside>

      <div className={s.scrim} onClick={() => setNavOpen(false)} aria-hidden="true" />

      <main className={s.main}>
        <header className={s.topBar} data-mobile-only>
          <button type="button" className={s.iconButton} onClick={() => setNavOpen(true)} aria-label="Open menu"><Menu size={20} strokeWidth={1.75} /></button>
          <span className={s.topTitle}>{chatId ? chats.find(c => c.id === chatId)?.title : 'Syncra'}</span>
          <a href="#/" className={s.iconButton} aria-label="New chat"><Plus size={20} strokeWidth={1.75} /></a>
        </header>
        <Suspense>{children}</Suspense>
      </main>
    </div>
  )
}

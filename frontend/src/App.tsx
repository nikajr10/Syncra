import { lazy, Suspense, useCallback, useEffect, useState } from 'react'
import { Activity, CheckSquare, LogOut, Menu, Plus, Unplug, Users, X } from 'lucide-react'
import { api, setOnUnauthorized, token, type Card, type Chat, type Me } from '@/api'
import { Badge } from '@/components/arc/badge/badge'
import { Approvals, ChatView } from './Chat'
import Login from './Login'
import { go, useHash } from './ui'
import s from './App.module.css'

// Admin pages load on first visit, so other users never download them.
const SourcesPage = lazy(() => import('./Admin').then(m => ({ default: m.SourcesPage })))
const PeoplePage = lazy(() => import('./Admin').then(m => ({ default: m.PeoplePage })))
const ActivityPage = lazy(() => import('./Admin').then(m => ({ default: m.ActivityPage })))

export default function App() {
  const [me, setMe] = useState<Me | null | undefined>(() => (token.get() ? undefined : null)) // undefined while checking the saved token

  useEffect(() => {
    setOnUnauthorized(() => { token.set(null); setMe(null) })
    if (token.get()) api.me().then(setMe, () => setMe(null))
  }, [])

  if (me === undefined) return null
  if (me === null) return <Login onLogin={setMe} />
  return <Shell me={me} onSignOut={async () => { await api.logout().catch(() => {}); token.set(null); setMe(null); go('/') }} />
}

function Shell({ me, onSignOut }: { me: Me; onSignOut: () => Promise<void> }) {
  const hash = useHash()
  const [chats, setChats] = useState<Chat[]>([])
  const [actions, setActions] = useState<Card[]>([])
  const [navOpen, setNavOpen] = useState(false)

  const loadChats = useCallback(() => api.chats().then(setChats, () => {}), [])
  const loadActions = useCallback(() => api.actions().then(setActions, () => {}), [])
  useEffect(() => {
    // Live: approvals and chats from other tabs or devices show up without a reload.
    const refresh = () => { if (document.visibilityState === 'visible') { loadChats(); loadActions() } }
    refresh()
    const timer = setInterval(refresh, 30_000)
    addEventListener('focus', refresh)
    document.addEventListener('visibilitychange', refresh)
    return () => { clearInterval(timer); removeEventListener('focus', refresh); document.removeEventListener('visibilitychange', refresh) }
  }, [loadChats, loadActions])

  const chatMatch = /^\/chat\/(\d+)$/.exec(hash)
  const chatId = chatMatch ? Number(chatMatch[1]) : null
  const pending = actions.filter(a => a.status === 'pending').length
  const updateCard = (card: Card) => setActions(list => list.map(a => (a.id === card.id ? card : a)))

  const pages = [
    { path: '/approvals', label: 'Approvals', icon: CheckSquare, admin: false },
    { path: '/sources', label: 'Sources', icon: Unplug, admin: true },
    { path: '/people', label: 'People', icon: Users, admin: true },
    { path: '/activity', label: 'Activity', icon: Activity, admin: true },
  ].filter(p => !p.admin || me.is_admin)

  let main
  if (hash === '/approvals') main = <Approvals actions={actions} onChange={updateCard} />
  else if (hash === '/sources' && me.is_admin) main = <SourcesPage />
  else if (hash === '/people' && me.is_admin) main = <PeoplePage />
  else if (hash === '/activity' && me.is_admin) main = <ActivityPage />
  else main = (
    <ChatView
      chatId={chatId}
      name={me.display_name?.split(' ')[0] ?? me.username}
      actions={actions}
      onChatCreated={chat => { setChats(list => [chat, ...list]); go(`/chat/${chat.id}`) }}
      onReplied={() => { loadChats(); loadActions() }}
      onCardChange={updateCard}
    />
  )

  return (
    <div className={s.shell} data-nav-open={navOpen || undefined}>
      <aside className={s.sidebar} aria-label="Chats and pages" onClick={e => { if ((e.target as Element).closest('a')) setNavOpen(false) }}>
        <div className={s.brandRow}>
          <a href="#/" className={s.brand}><img src="/favicon.svg" alt="" width={24} height={24} />Syncra</a>
          <button type="button" className={s.iconButton} onClick={() => setNavOpen(false)} aria-label="Close menu" data-mobile-only><X size={20} strokeWidth={1.75} /></button>
        </div>

        <a href="#/" className={s.newChat}><Plus size={16} strokeWidth={1.75} aria-hidden="true" />New chat</a>

        <nav className={s.chatList} aria-label="Chats">
          {chats.length === 0 && <p className={s.muted}>Your chats will show up here.</p>}
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
          <button type="button" className={s.iconButton} onClick={onSignOut} aria-label="Sign out" title="Sign out"><LogOut size={18} strokeWidth={1.75} /></button>
        </div>
      </aside>

      <div className={s.scrim} onClick={() => setNavOpen(false)} aria-hidden="true" />

      <main className={s.main}>
        <header className={s.topBar} data-mobile-only>
          <button type="button" className={s.iconButton} onClick={() => setNavOpen(true)} aria-label="Open menu"><Menu size={20} strokeWidth={1.75} /></button>
          <span className={s.topTitle}>{chatId ? chats.find(c => c.id === chatId)?.title : 'Syncra'}</span>
          <a href="#/" className={s.iconButton} aria-label="New chat"><Plus size={20} strokeWidth={1.75} /></a>
        </header>
        <Suspense>{main}</Suspense>
      </main>
    </div>
  )
}

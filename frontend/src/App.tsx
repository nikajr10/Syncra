import { useCallback, useEffect, useState } from 'react'
import { Activity, CheckSquare, Menu, Plus, Search, Unplug, Users, X } from 'lucide-react'
import { api, setOnUnauthorized, token, type Card, type Chat, type Me } from '@/api'
import { Badge } from '@/components/arc/badge/badge'
import { CommandPalette, type CommandItem } from '@/components/arc/command-palette/command-palette'
import { Dialog, DialogContent } from '@/components/arc/dialog/dialog'
import { ToastStack, ToastStackProvider } from '@/components/arc/toast-stack/toast-stack'
import { UserMenu, type ThemePreference } from '@/components/arc/user-menu/user-menu'
import { ActivityPage, PeoplePage, SourcesPage } from './Admin'
import { Approvals, ChatView } from './Chat'
import Login from './Login'
import { go, timeAgo, useHash } from './ui'
import s from './App.module.css'

export default function App() {
  const [me, setMe] = useState<Me | null | undefined>(() => (token.get() ? undefined : null)) // undefined while checking the saved token

  useEffect(() => {
    setOnUnauthorized(() => { token.set(null); setMe(null) })
    if (token.get()) api.me().then(setMe, () => setMe(null))
  }, [])

  if (me === undefined) return null
  if (me === null) return <Login onLogin={setMe} />
  return (
    <ToastStackProvider>
      <Shell me={me} onSignOut={async () => { await api.logout().catch(() => {}); token.set(null); setMe(null); go('/') }} />
      <ToastStack />
    </ToastStackProvider>
  )
}

const THEME = 'syncra-theme'

function useTheme() {
  const [theme, setTheme] = useState<ThemePreference>(() => {
    try { return (localStorage.getItem(THEME) as ThemePreference) || 'system' } catch { return 'system' }
  })
  useEffect(() => {
    try { localStorage.setItem(THEME, theme) } catch { /* private mode */ }
    const dark = matchMedia('(prefers-color-scheme: dark)')
    const apply = () => { document.documentElement.dataset.theme = theme === 'system' ? (dark.matches ? 'dark' : 'light') : theme }
    apply()
    dark.addEventListener('change', apply)
    return () => dark.removeEventListener('change', apply)
  }, [theme])
  return [theme, setTheme] as const
}

function Shell({ me, onSignOut }: { me: Me; onSignOut: () => Promise<void> }) {
  const hash = useHash()
  const [theme, setTheme] = useTheme()
  const [chats, setChats] = useState<Chat[]>([])
  const [actions, setActions] = useState<Card[]>([])
  const [navOpen, setNavOpen] = useState(false)
  const [paletteOpen, setPaletteOpen] = useState(false)

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

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') { e.preventDefault(); setPaletteOpen(o => !o) }
    }
    addEventListener('keydown', onKey)
    return () => removeEventListener('keydown', onKey)
  }, [])

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

  // Arc builds element ids from item ids, so ids are the paths with dots for slashes.
  const commands: CommandItem[] = [
    { id: '.', label: 'New chat', group: 'Actions', icon: <Plus size={16} strokeWidth={1.75} /> },
    ...pages.map(p => ({ id: p.path.replaceAll('/', '.'), label: p.label, group: 'Go to', icon: <p.icon size={16} strokeWidth={1.75} /> })),
    ...chats.map(c => ({ id: `.chat.${c.id}`, label: c.title || 'Untitled chat', description: timeAgo(c.updated_at), group: 'Chats' })),
  ]

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

        <div className={s.actionsRow}>
          <a href="#/" className={s.newChat}><Plus size={16} strokeWidth={1.75} aria-hidden="true" />New chat</a>
          <button type="button" className={s.searchButton} onClick={() => setPaletteOpen(true)} aria-label="Search chats and pages" aria-keyshortcuts="Meta+K">
            <Search size={16} strokeWidth={1.75} aria-hidden="true" /><kbd>⌘K</kbd>
          </button>
        </div>

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
          <UserMenu
            user={{ name: me.display_name || me.username, email: `@${me.username}`, plan: me.is_admin ? 'Admin' : undefined }}
            showName
            align="start"
            theme={theme}
            onThemeChange={setTheme}
            onSignOut={onSignOut}
          />
        </div>
      </aside>

      <div className={s.scrim} onClick={() => setNavOpen(false)} aria-hidden="true" />

      <main className={s.main}>
        <header className={s.topBar} data-mobile-only>
          <button type="button" className={s.iconButton} onClick={() => setNavOpen(true)} aria-label="Open menu"><Menu size={20} strokeWidth={1.75} /></button>
          <span className={s.topTitle}>{chatId ? chats.find(c => c.id === chatId)?.title : 'Syncra'}</span>
          <a href="#/" className={s.iconButton} aria-label="New chat"><Plus size={20} strokeWidth={1.75} /></a>
        </header>
        {main}
      </main>

      <Dialog open={paletteOpen} onOpenChange={setPaletteOpen}>
        <DialogContent title="Search">
          <CommandPalette
            items={commands}
            placeholder="Search chats and pages"
            autoFocus
            onSelect={item => { go(item.id.replaceAll('.', '/')); setPaletteOpen(false) }}
            onClose={() => setPaletteOpen(false)}
          />
        </DialogContent>
      </Dialog>
    </div>
  )
}

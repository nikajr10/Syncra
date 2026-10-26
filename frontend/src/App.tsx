import { lazy, type ComponentType } from 'react'
import { Shell } from '@/components/layout/Shell'
import { useMe } from '@/hooks/useAuth'
import { useHash } from '@/hooks/useHash'
import ApprovalsPage from '@/pages/ApprovalsPage'
import ChatPage from '@/pages/ChatPage'
import LoginPage from '@/pages/LoginPage'

// Admin pages load on first visit, so other users never download them.
const ADMIN_PAGES: Record<string, ComponentType> = {
  '/sources': lazy(() => import('@/pages/admin/SourcesPage')),
  '/people': lazy(() => import('@/pages/admin/PeoplePage')),
  '/activity': lazy(() => import('@/pages/admin/ActivityPage')),
}

export default function App() {
  const { data: me, isPending } = useMe()
  const hash = useHash()

  if (isPending) return null // checking the saved token
  if (!me) return <LoginPage />

  const chatId = Number(/^\/chat\/(\d+)$/.exec(hash)?.[1]) || null
  const AdminPage = me.is_admin ? ADMIN_PAGES[hash] : undefined
  return (
    <Shell me={me} hash={hash} chatId={chatId}>
      {hash === '/approvals'
        ? <ApprovalsPage />
        : AdminPage
        ? <AdminPage />
        : <ChatPage chatId={chatId} name={me.display_name?.split(' ')[0] ?? me.username} />}
    </Shell>
  )
}

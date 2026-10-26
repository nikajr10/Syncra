// Every API call the app makes. Components reach these through the hooks in src/hooks.

import { json, send, takeEvents } from './client'
import type { Account, Card, Chat, Me, Message, Reply, SourceView, Status, Suggestions, Tool, UserView } from './types'

export const api = {
  login: (username: string, password: string) => json<{ token: string }>('POST', '/auth/login', { username, password }),
  logout: () => json<null>('POST', '/auth/logout'),
  me: () => json<Me>('GET', '/me'),
  chats: () => json<Chat[]>('GET', '/chat/sessions'),
  newChat: (title: string) => json<Chat>('POST', '/chat/sessions', { title }),
  messages: (id: number) => json<Message[]>('GET', `/chat/sessions/${id}/messages`),
  suggestions: () => json<Suggestions>('GET', '/chat/suggestions'),
  actions: () => json<Card[]>('GET', '/actions'),
  approve: (id: number) => json<Card>('POST', `/actions/${id}/approve`),
  reject: (id: number) => json<Card>('POST', `/actions/${id}/reject`),
  sources: () => json<{ tools: Record<Tool, boolean>; sources: SourceView[] }>('GET', '/admin/sources'),
  addSource: (kind: Tool, external_id: string, name: string) =>
    json<SourceView>('POST', '/admin/sources', { kind, external_id, name: name || null }),
  setSource: (id: number, enabled: boolean) => json<SourceView>('PATCH', `/admin/sources/${id}`, { enabled }),
  syncSource: (id: number) => json<SourceView>('POST', `/admin/sources/${id}/sync`),
  users: () => json<UserView[]>('GET', '/admin/users'),
  linkAccount: (username: string, tool: Tool, account_id: string, display_name: string) =>
    json<Account>('POST', `/admin/users/${encodeURIComponent(username)}/accounts`, { tool, account_id, display_name }),
  status: () => json<Status>('GET', '/admin/status'),
}

/** POST a message and read the Server-Sent Events: `token` pieces of the draft, then the saved `done` reply. */
export async function streamMessage(chatId: number, message: string, onToken: (text: string) => void): Promise<Reply> {
  const res = await send('POST', `/chat/sessions/${chatId}/messages/stream`, { message })
  const reader = res.body!.pipeThrough(new TextDecoderStream()).getReader()
  let buffer = ''
  for (;;) {
    const { value, done } = await reader.read()
    if (done) break
    const { events, rest } = takeEvents(buffer + value)
    buffer = rest
    for (const { event, data } of events) {
      if (event === 'token') onToken((data as { text: string }).text)
      if (event === 'done') return data as Reply
    }
  }
  throw new Error('The answer stopped before it finished. Try again.')
}

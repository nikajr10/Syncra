// The Syncra API, reached through Vite's /api proxy (vite.config.ts). Shapes mirror backend/app/api.

export interface Account { tool: Tool; id: string; display_name: string | null }
export interface Me { username: string; display_name: string | null; is_admin: boolean; accounts: Account[] }
export interface Chat { id: number; title: string | null; updated_at: string }
export interface Source {
  label: string; title: string | null; link: string | null; type: string
  author: string | null; date: string | null; excerpt: string
}
export interface Message {
  role: 'user' | 'assistant'; content: string; sources: Source[]
  confidence: Confidence | null; created_at: string
}
export type Confidence = 'high' | 'medium' | 'low'
export interface Card {
  id: number; session_id: number | null; kind: string
  payload: { project: string; title: string; description?: string }
  status: 'pending' | 'approved' | 'rejected' | 'done' | 'failed'
  result: { key?: string; link?: string; error?: string } | null
  created_at: string
}
export interface Reply {
  path: 'small_talk' | 'question' | 'action' | 'blocked'; reply: string; question: string | null
  sources: Source[]; confidence: Confidence | null; follow_ups: string[]; action: Card | null
}
export type Tool = 'github' | 'jira' | 'slack'
export interface SourceView {
  id: number; kind: Tool; name: string; external_id: string; enabled: boolean
  last_synced_at: string | null; last_error: string | null; items: number; members: number
}
export interface UserView { username: string; display_name: string | null; is_admin: boolean; accounts: Account[] }
export interface EventView { kind: string; message: string; details: Record<string, unknown>; created_at: string }
export interface Status { items: Record<string, number>; sources: SourceView[]; events: EventView[] }

const TOKEN = 'syncra-token'

export const token = {
  get: () => { try { return localStorage.getItem(TOKEN) } catch { return null } },
  set: (value: string | null) => {
    try { if (value) localStorage.setItem(TOKEN, value); else localStorage.removeItem(TOKEN) } catch { /* private mode */ }
  },
}

/** Called when the API says the token is no longer valid; App sends the user back to login. */
export let onUnauthorized = () => {}
export const setOnUnauthorized = (fn: () => void) => { onUnauthorized = fn }

async function send(method: string, path: string, body?: unknown): Promise<Response> {
  const headers: Record<string, string> = {}
  const t = token.get()
  if (t) headers.Authorization = `Bearer ${t}`
  if (body !== undefined) headers['Content-Type'] = 'application/json'
  const res = await fetch(`/api${path}`, { method, headers, body: body === undefined ? undefined : JSON.stringify(body) })
  if (res.status === 401 && path !== '/auth/login') onUnauthorized()
  if (!res.ok) throw new Error(await detail(res))
  return res
}

async function detail(res: Response): Promise<string> {
  try {
    const d = (await res.json()).detail
    if (typeof d === 'string') return d
    if (Array.isArray(d) && d[0]?.msg) return d[0].msg // pydantic validation
  } catch { /* not json */ }
  return res.status >= 500 ? 'The server had a problem. Try again in a moment.' : `Request failed (${res.status})`
}

const json = async <T>(method: string, path: string, body?: unknown): Promise<T> => {
  const res = await send(method, path, body)
  return (res.status === 204 ? null : res.json()) as T
}

export const api = {
  login: (username: string, password: string) => json<{ token: string }>('POST', '/auth/login', { username, password }),
  logout: () => json<null>('POST', '/auth/logout'),
  me: () => json<Me>('GET', '/me'),
  chats: () => json<Chat[]>('GET', '/chat/sessions'),
  newChat: (title: string) => json<Chat>('POST', '/chat/sessions', { title }),
  messages: (id: number) => json<Message[]>('GET', `/chat/sessions/${id}/messages`),
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

/** Complete Server-Sent Events at the front of `buffer`, and what is left: the start of the next one. */
export function takeEvents(buffer: string): { events: { event: string; data: unknown }[]; rest: string } {
  const blocks = buffer.split('\n\n')
  const rest = blocks.pop()!
  const events = blocks.map(block => ({
    event: /^event: (.*)$/m.exec(block)?.[1] ?? 'message',
    data: JSON.parse(/^data: (.*)$/m.exec(block)?.[1] ?? 'null'),
  }))
  return { events, rest }
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

// HTTP transport for the Syncra API, reached through Vite's /api proxy (vite.config.ts).

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

export async function send(method: string, path: string, body?: unknown): Promise<Response> {
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

export const json = async <T>(method: string, path: string, body?: unknown): Promise<T> => {
  const res = await send(method, path, body)
  return (res.status === 204 ? null : res.json()) as T
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

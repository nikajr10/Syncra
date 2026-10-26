import { useQuery, useQueryClient } from '@tanstack/react-query'
import { api, streamMessage } from '@/api/endpoints'
import type { Chat, Message, Reply } from '@/api/types'
import { go } from './useHash'

/** A message on screen: a saved one, or the reply being streamed into place. */
export interface Turn extends Partial<Omit<Message, 'role'>> {
  role: Message['role']
  content: string
  streaming?: boolean
  path?: Reply['path']
  followUps?: string[]
  actionId?: number
  error?: string
}

type ChatKey = number | 'new' // 'new': the chat that is created with its first message
const messagesKey = (chat: ChatKey) => ['messages', chat] as const

/** The user's chats, newest first. Polled so chats from other tabs or devices show up. */
export function useChats() {
  return useQuery({ queryKey: ['chats'], queryFn: api.chats, refetchInterval: 30_000 })
}

/** A chat's turns. Streamed replies are written into this cache, so it is never refetched while open. */
export function useMessages(chatId: number | null) {
  return useQuery<Turn[]>({
    queryKey: messagesKey(chatId ?? 'new'),
    queryFn: () => (chatId === null ? [] : api.messages(chatId)),
    staleTime: Infinity,
  })
}

/** Starter questions for an empty chat (GET /chat/suggestions). */
export function useSuggestions(enabled: boolean) {
  return useQuery({ queryKey: ['suggestions'], queryFn: api.suggestions, enabled, staleTime: 60_000 })
}

/** Send a message: create the chat if needed, stream the reply into its cache, then refresh the lists. */
export function useSendMessage() {
  const qc = useQueryClient()
  const patchLast = (chat: ChatKey, patch: Partial<Turn> | ((t: Turn) => Partial<Turn>)) =>
    qc.setQueryData<Turn[]>(messagesKey(chat), list =>
      list?.map((t, i) => (i === list.length - 1 ? { ...t, ...(typeof patch === 'function' ? patch(t) : patch) } : t)))

  return async (chatId: number | null, text: string) => {
    let chat: ChatKey = chatId ?? 'new'
    qc.setQueryData<Turn[]>(messagesKey(chat), list => [
      ...(list ?? []), { role: 'user', content: text }, { role: 'assistant', content: '', streaming: true },
    ])
    try {
      if (chat === 'new') {
        const created = await api.newChat(text.length > 80 ? `${text.slice(0, 77)}…` : text)
        qc.setQueryData(messagesKey(created.id), qc.getQueryData(messagesKey('new')))
        qc.removeQueries({ queryKey: messagesKey('new') })
        qc.setQueryData<Chat[]>(['chats'], list => [created, ...(list ?? [])])
        chat = created.id
        go(`/chat/${created.id}`)
      }
      const id = chat
      const reply = await streamMessage(id, text, piece => patchLast(id, t => ({ content: t.content + piece })))
      patchLast(id, {
        content: reply.reply, streaming: false, path: reply.path, sources: reply.sources,
        confidence: reply.confidence, followUps: reply.follow_ups, actionId: reply.action?.id,
      })
      qc.invalidateQueries({ queryKey: ['chats'] })
      qc.invalidateQueries({ queryKey: ['actions'] })
    } catch (err) {
      patchLast(chat, { streaming: false, error: err instanceof Error ? err.message : 'Something went wrong' })
    }
  }
}

// Shapes returned by the Syncra API; they mirror the Pydantic models in backend/app/schemas.

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
export interface Suggestions { questions: string[]; ticket_project: string | null }

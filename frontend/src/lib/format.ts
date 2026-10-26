// Small formatting helpers shared by the pages.

import type { Tool } from '@/api/types'

export const TOOLS: Tool[] = ['github', 'jira', 'slack']
export const TOOL_NAME: Record<Tool, string> = { github: 'GitHub', jira: 'Jira', slack: 'Slack' }
export const toolOptions = TOOLS.map(t => ({ value: t, label: TOOL_NAME[t] }))

/** Which tool an item type or link came from, for the brand mark beside a source. */
export function toolOf(type: string, link: string | null): Tool | null {
  let host = ''
  try { host = new URL(link ?? '').hostname } catch { /* no link */ }
  if (/(^|\.)github\./.test(host) || ['pr', 'review', 'commit'].includes(type)) return 'github'
  if (/(^|\.)slack\./.test(host) || ['message', 'thread'].includes(type)) return 'slack'
  if (/(^|\.)atlassian\./.test(host) || link?.includes('/browse/') || type === 'issue') return 'jira'
  return null
}

const TYPE_NAME: Record<string, string> = {
  pr: 'Pull request', review: 'Review', commit: 'Commit', issue: 'Ticket',
  comment: 'Comment', message: 'Message', thread: 'Thread', decision: 'Decision',
}

export const typeName = (type: string) => TYPE_NAME[type] ?? type.charAt(0).toUpperCase() + type.slice(1)

const units: [Intl.RelativeTimeFormatUnit, number][] = [['year', 31536e6], ['month', 2592e6], ['week', 6048e5], ['day', 864e5], ['hour', 36e5], ['minute', 6e4]]
const rtf = new Intl.RelativeTimeFormat('en', { numeric: 'auto' })

export function timeAgo(iso: string, now = Date.now()): string {
  const diff = new Date(iso).getTime() - now
  for (const [unit, ms] of units) if (Math.abs(diff) >= ms) return rtf.format(Math.round(diff / ms), unit)
  return 'just now'
}

/** Links come from the tools' data: only http(s) becomes a link. */
export const safeUrl = (url: string | null | undefined) => (url && /^https?:\/\//i.test(url) ? url : undefined)

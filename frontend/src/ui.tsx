import { useEffect, useState } from 'react'
import { CircleDot, FileText, GitCommitHorizontal, GitPullRequest, Lightbulb, MessageSquareCode, MessagesSquare } from 'lucide-react'
import type { Tool } from '@/api'
import s from './ui.module.css'

// Brand marks from simple-icons, in their own colors (Arc: third-party logos keep their colors).
export function BrandIcon({ tool, size = 16 }: { tool: Tool; size?: number }) {
  const common = { width: size, height: size, viewBox: '0 0 24 24', 'aria-hidden': true, className: s.brand }
  if (tool === 'github') return (
    <svg {...common} data-tool="github"><path fill="currentColor" d="M12 .297c-6.63 0-12 5.373-12 12 0 5.303 3.438 9.8 8.205 11.385.6.113.82-.258.82-.577 0-.285-.01-1.04-.015-2.04-3.338.724-4.042-1.61-4.042-1.61C4.422 18.07 3.633 17.7 3.633 17.7c-1.087-.744.084-.729.084-.729 1.205.084 1.838 1.236 1.838 1.236 1.07 1.835 2.809 1.305 3.495.998.108-.776.417-1.305.76-1.605-2.665-.3-5.466-1.332-5.466-5.93 0-1.31.465-2.38 1.235-3.22-.135-.303-.54-1.523.105-3.176 0 0 1.005-.322 3.3 1.23.96-.267 1.98-.399 3-.405 1.02.006 2.04.138 3 .405 2.28-1.552 3.285-1.23 3.285-1.23.645 1.653.24 2.873.12 3.176.765.84 1.23 1.91 1.23 3.22 0 4.61-2.805 5.625-5.475 5.92.42.36.81 1.096.81 2.22 0 1.606-.015 2.896-.015 3.286 0 .315.21.69.825.57C20.565 22.092 24 17.592 24 12.297c0-6.627-5.373-12-12-12" /></svg>
  )
  if (tool === 'jira') return (
    <svg {...common} data-tool="jira"><path fill="#2684FF" d="M11.571 11.513H0a5.218 5.218 0 0 0 5.232 5.215h2.13v2.057A5.215 5.215 0 0 0 12.575 24V12.518a1.005 1.005 0 0 0-1.005-1.005zm5.723-5.756H5.736a5.215 5.215 0 0 0 5.215 5.214h2.129v2.058a5.218 5.218 0 0 0 5.215 5.214V6.758a1.001 1.001 0 0 0-1.001-1.001zM23.013 0H11.455a5.215 5.215 0 0 0 5.215 5.215h2.129v2.057A5.215 5.215 0 0 0 24 12.483V1.005A1.001 1.001 0 0 0 23.013 0Z" /></svg>
  )
  return (
    <svg {...common} data-tool="slack">
      <path fill="#E01E5A" d="M5.042 15.165a2.528 2.528 0 0 1-2.52 2.523A2.528 2.528 0 0 1 0 15.165a2.527 2.527 0 0 1 2.522-2.52h2.52v2.52zM6.313 15.165a2.527 2.527 0 0 1 2.521-2.52 2.527 2.527 0 0 1 2.521 2.52v6.313A2.528 2.528 0 0 1 8.834 24a2.528 2.528 0 0 1-2.521-2.522v-6.313z" />
      <path fill="#36C5F0" d="M8.834 5.042a2.528 2.528 0 0 1-2.521-2.52A2.528 2.528 0 0 1 8.834 0a2.528 2.528 0 0 1 2.521 2.522v2.52H8.834zM8.834 6.313a2.528 2.528 0 0 1 2.521 2.521 2.528 2.528 0 0 1-2.521 2.521H2.522A2.528 2.528 0 0 1 0 8.834a2.528 2.528 0 0 1 2.522-2.521h6.312z" />
      <path fill="#2EB67D" d="M18.956 8.834a2.528 2.528 0 0 1 2.522-2.521A2.528 2.528 0 0 1 24 8.834a2.528 2.528 0 0 1-2.522 2.521h-2.522V8.834zM17.688 8.834a2.528 2.528 0 0 1-2.523 2.521 2.527 2.527 0 0 1-2.52-2.521V2.522A2.527 2.527 0 0 1 15.165 0a2.528 2.528 0 0 1 2.523 2.522v6.312z" />
      <path fill="#ECB22E" d="M15.165 18.956a2.528 2.528 0 0 1 2.523 2.522A2.528 2.528 0 0 1 15.165 24a2.527 2.527 0 0 1-2.52-2.522v-2.522h2.52zM15.165 17.688a2.527 2.527 0 0 1-2.52-2.523 2.526 2.526 0 0 1 2.52-2.52h6.313A2.527 2.527 0 0 1 24 15.165a2.528 2.528 0 0 1-2.522 2.523h-6.313z" />
    </svg>
  )
}

export const TOOL_NAME: Record<Tool, string> = { github: 'GitHub', jira: 'Jira', slack: 'Slack' }

/** Which tool an item type or link came from, for the brand mark beside a source. */
export function toolOf(type: string, link: string | null): Tool | null {
  let host = ''
  try { host = new URL(link ?? '').hostname } catch { /* no link */ }
  if (/(^|\.)github\./.test(host) || ['pr', 'review', 'commit'].includes(type)) return 'github'
  if (/(^|\.)slack\./.test(host) || ['message', 'thread'].includes(type)) return 'slack'
  if (/(^|\.)atlassian\./.test(host) || link?.includes('/browse/') || type === 'issue') return 'jira'
  return null
}

const TYPE_ICON: Record<string, typeof FileText> = {
  pr: GitPullRequest, review: MessageSquareCode, commit: GitCommitHorizontal,
  issue: CircleDot, message: MessagesSquare, thread: MessagesSquare, decision: Lightbulb,
}
const TYPE_NAME: Record<string, string> = {
  pr: 'Pull request', review: 'Review', commit: 'Commit', issue: 'Ticket',
  comment: 'Comment', message: 'Message', thread: 'Thread', decision: 'Decision',
}

export function TypeIcon({ type, size = 16 }: { type: string; size?: number }) {
  const Icon = TYPE_ICON[type] ?? FileText
  return <Icon size={size} strokeWidth={1.75} aria-hidden="true" />
}
export const typeName = (type: string) => TYPE_NAME[type] ?? type.charAt(0).toUpperCase() + type.slice(1)

const units: [Intl.RelativeTimeFormatUnit, number][] = [['year', 31536e6], ['month', 2592e6], ['week', 6048e5], ['day', 864e5], ['hour', 36e5], ['minute', 6e4]]
const rtf = new Intl.RelativeTimeFormat('en', { numeric: 'auto' })

export function timeAgo(iso: string, now = Date.now()): string {
  const diff = new Date(iso).getTime() - now
  for (const [unit, ms] of units) if (Math.abs(diff) >= ms) return rtf.format(Math.round(diff / ms), unit)
  return 'just now'
}

/** The part of the URL after `#`, so a reload or a shared link opens the same screen. */
export function useHash(): string {
  const [hash, setHash] = useState(() => location.hash.slice(1) || '/')
  useEffect(() => {
    const update = () => setHash(location.hash.slice(1) || '/')
    addEventListener('hashchange', update)
    return () => removeEventListener('hashchange', update)
  }, [])
  return hash
}
export const go = (path: string) => { location.hash = path }

import { useState, type FormEvent } from 'react'
import type { Tool, UserView } from '@/api/types'
import { Alert } from '@/components/arc/alert/alert'
import { Badge } from '@/components/arc/badge/badge'
import { Button } from '@/components/arc/button/button'
import { Dialog, DialogContent } from '@/components/arc/dialog/dialog'
import { EmptyState } from '@/components/arc/empty-state/empty-state'
import { Input } from '@/components/arc/input/input'
import { Select } from '@/components/arc/select/select'
import { Skeleton } from '@/components/arc/skeleton/skeleton'
import { Page } from '@/components/layout/Page'
import { BrandIcon } from '@/components/ToolIcon'
import { useLinkAccount, useUsers } from '@/hooks/useAdmin'
import { toolOptions } from '@/lib/format'
import s from './admin.module.css'

const ACCOUNT_HINT: Record<Tool, string> = {
  github: 'GitHub username, e.g. alice-chen',
  jira: 'Jira accountId, from the profile URL',
  slack: 'Slack member ID, e.g. U0123ABCD',
}

export default function PeoplePage() {
  const { data, error } = useUsers()
  const [linking, setLinking] = useState<UserView | null>(null)

  return (
    <Page title="People">
      {error && <Alert tone="danger" title="Failed to load people">{error.message}</Alert>}
      {!data && !error && <Skeleton lines={4} />}
      {data?.length === 0 && <EmptyState title="No users" description="Create users with make add-user." />}
      {data && data.length > 0 && (
        <ul className={s.list} aria-label="People">
          {data.map(u => (
            <li key={u.username} className={s.row}>
              <div className={s.rowMain}>
                <div className={s.rowTitle}>
                  <span className={s.name}>{u.display_name || u.username}</span>
                  <span className={s.muted}>@{u.username}</span>
                  {u.is_admin && <Badge tone="info" size="sm">Admin</Badge>}
                </div>
                <div className={s.accounts}>
                  {u.accounts.length === 0 && <span className={s.warn}>No linked accounts</span>}
                  {u.accounts.map(a => (
                    <span key={`${a.tool}:${a.id}`} className={s.account} title={a.display_name ?? undefined}>
                      <BrandIcon tool={a.tool} size={14} />{a.id}
                    </span>
                  ))}
                </div>
              </div>
              <div className={s.rowActions}>
                <Button variant="secondary" size="sm" onClick={() => setLinking(u)}>Link account</Button>
              </div>
            </li>
          ))}
        </ul>
      )}
      <LinkAccount user={linking} onClose={() => setLinking(null)} />
    </Page>
  )
}

function LinkAccount({ user, onClose }: { user: UserView | null; onClose: () => void }) {
  const [tool, setTool] = useState<Tool>('github')
  const link = useLinkAccount()

  function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault()
    if (!user) return
    const form = new FormData(e.currentTarget)
    link.mutate(
      { username: user.username, tool, accountId: String(form.get('account_id')).trim(), displayName: String(form.get('display_name')).trim() },
      { onSuccess: onClose },
    )
  }

  return (
    <Dialog open={!!user} onOpenChange={o => { if (!o) { onClose(); link.reset() } }}>
      <DialogContent title={`Link an account to ${user?.display_name || user?.username || ''}`} description="An account can be linked to one user only.">
        <form className={s.form} onSubmit={submit}>
          <Select label="Tool" options={toolOptions} value={tool} onValueChange={v => setTool(v as Tool)} />
          <Input label="Account id" description={ACCOUNT_HINT[tool]} name="account_id" required autoComplete="off" spellCheck={false} />
          <Input label="Display name" description="Optional" name="display_name" autoComplete="off" />
          <Alert tone="danger" title="Failed to link account" open={link.isError}>{link.error?.message}</Alert>
          <div className={s.formActions}>
            <Button type="button" variant="ghost" onClick={onClose}>Cancel</Button>
            <Button type="submit" variant="primary" loading={link.isPending}>Link account</Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  )
}

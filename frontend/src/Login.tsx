import { useState, type FormEvent } from 'react'
import { api, token, type Me } from '@/api'
import { Alert } from '@/components/arc/alert/alert'
import { Button } from '@/components/arc/button/button'
import { Input } from '@/components/arc/input/input'
import { PasswordField } from '@/components/arc/password-field/password-field'
import { BrandIcon } from './ui'
import s from './Login.module.css'

export default function Login({ onLogin }: { onLogin: (me: Me) => void }) {
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault()
    const form = new FormData(e.currentTarget)
    setBusy(true)
    setError('')
    try {
      const { token: t } = await api.login(String(form.get('username')), String(form.get('password')))
      token.set(t)
      onLogin(await api.me())
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not sign in')
      setBusy(false)
    }
  }

  return (
    <div className={s.page}>
      <svg className={s.rings} viewBox="0 0 800 800" aria-hidden="true">
        {[120, 200, 280, 360].map(r => <circle key={r} cx="400" cy="400" r={r} />)}
      </svg>
      <main className={s.card}>
        <img src="/favicon.svg" alt="" width={40} height={40} className={s.logo} />
        <h1 className={s.title}>Sign in to Syncra</h1>
        <p className={s.lead}>Ask what your team knows. Every answer shows where it came from.</p>
        <div className={s.tools} role="img" aria-label="Learns from GitHub, Jira and Slack">
          <BrandIcon tool="github" /><BrandIcon tool="jira" /><BrandIcon tool="slack" />
        </div>
        <form className={s.form} onSubmit={submit}>
          <Input label="Username" name="username" autoComplete="username" autoCapitalize="none" spellCheck={false} required autoFocus />
          <PasswordField label="Password" name="password" autoComplete="current-password" required />
          <Alert tone="danger" title="Couldn't sign you in" open={!!error}>{error}</Alert>
          <Button type="submit" variant="primary" size="lg" loading={busy}>Sign in</Button>
        </form>
        <p className={s.footnote}>No account yet? An admin creates one with <code>make add-user</code>.</p>
      </main>
    </div>
  )
}

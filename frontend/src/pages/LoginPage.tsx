import { type FormEvent } from 'react'
import { Alert } from '@/components/arc/alert/alert'
import { Button } from '@/components/arc/button/button'
import { Input } from '@/components/arc/input/input'
import { PasswordField } from '@/components/arc/password-field/password-field'
import { useLogin } from '@/hooks/useAuth'
import s from './LoginPage.module.css'

export default function LoginPage() {
  const login = useLogin()

  function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault()
    const form = new FormData(e.currentTarget)
    login.mutate({ username: String(form.get('username')), password: String(form.get('password')) })
  }

  return (
    <div className={s.page}>
      <main className={s.card}>
        <img src="/favicon.svg" alt="" width={40} height={40} className={s.logo} />
        <h1 className={s.title}>Sign in to Syncra</h1>
        <form className={s.form} onSubmit={submit}>
          <Input label="Username" name="username" autoComplete="username" autoCapitalize="none" spellCheck={false} required autoFocus />
          <PasswordField label="Password" name="password" autoComplete="current-password" required />
          <Alert tone="danger" title="Sign-in failed" open={login.isError}>{login.error?.message}</Alert>
          <Button type="submit" variant="primary" size="lg" loading={login.isPending}>Sign in</Button>
        </form>
      </main>
    </div>
  )
}

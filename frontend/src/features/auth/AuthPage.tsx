/**
 * Autentificare — register / login.
 *
 * Implements the design prototype's Autentificare.dc.html: a dark brand panel
 * beside the form, with a register/login toggle.
 *
 * Retires Autentificare.dc.html.
 */

import { useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'

import { ApiError } from '@/lib/api-client'

import { useAuth } from './AuthContext'
import styles from './AuthPage.module.css'

type Mode = 'register' | 'login'

const MIN_PASSWORD_LENGTH = 10

export function AuthPage() {
  const { login, register } = useAuth()
  const navigate = useNavigate()

  const [mode, setMode] = useState<Mode>('register')
  const [fullName, setFullName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  const isRegister = mode === 'register'

  function switchTo(next: Mode) {
    setMode(next)
    // Errors belong to the attempt that caused them. Carrying "email already
    // registered" across to the login form would be nonsense.
    setError(null)
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    setError(null)
    setSubmitting(true)

    try {
      if (isRegister) {
        await register({ email, password, full_name: fullName })
      } else {
        await login({ email, password })
      }
      navigate('/catalog', { replace: true })
    } catch (caught) {
      // The API's message is already in Romanian and already careful not to
      // reveal whether an account exists. Rewriting it here would risk undoing
      // that, so it is shown as-is.
      setError(
        caught instanceof ApiError
          ? caught.message
          : 'A apărut o eroare neașteptată. Încearcă din nou.',
      )
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className={styles.page}>
      <aside className={styles.brand}>
        <div>
          <p className={styles.brandMark}>CONTRACTE.MD</p>
          <p className={styles.brandSub}>Crowe Turcan Mikhailenko</p>
        </div>

        <div>
          <div className={styles.badge}>
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="#F5A800" strokeWidth="2.2">
              <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
            </svg>
            <span>Contracte verificate juridic</span>
          </div>
          <h1 className={styles.brandTitle}>
            Contracte gata de semnat,
            <br />
            în câteva minute
          </h1>
          <p className={styles.brandText}>
            Alegi un contract, completezi datele, plătești și îl descarci în PDF și Word.
          </p>
        </div>

        <p className={styles.copyright}>© 2026 Crowe Turcan Mikhailenko</p>
      </aside>

      <main className={styles.formSide}>
        <div className={styles.formWrap}>
          <div className={styles.tabs} role="tablist">
            <button
              type="button"
              role="tab"
              aria-selected={isRegister}
              className={isRegister ? styles.tabOn : styles.tab}
              onClick={() => switchTo('register')}
            >
              Cont nou
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={!isRegister}
              className={!isRegister ? styles.tabOn : styles.tab}
              onClick={() => switchTo('login')}
            >
              Autentificare
            </button>
          </div>

          <h2 className={styles.heading}>
            {isRegister ? 'Creează-ți contul' : 'Bine ai revenit'}
          </h2>
          <p className={styles.sub}>
            {isRegister
              ? 'Ai nevoie de un cont pentru a cumpăra și descărca documente.'
              : 'Autentifică-te pentru a-ți accesa documentele.'}
          </p>

          <form onSubmit={handleSubmit} className={styles.form} noValidate>
            {/* Explicit htmlFor/id rather than wrapping the input in the label.
                A wrapping label absorbs everything inside it into the field's
                accessible name — the hint below would become part of the name
                a screen reader announces. aria-describedby attaches it as a
                description instead, which is what it is. */}
            {isRegister && (
              <div className={styles.field}>
                <label className={styles.label} htmlFor="full_name">
                  Nume complet
                </label>
                <input
                  id="full_name"
                  className={styles.input}
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  placeholder="Andrei Munteanu"
                  autoComplete="name"
                  required
                  minLength={2}
                />
              </div>
            )}

            <div className={styles.field}>
              <label className={styles.label} htmlFor="email">
                Email
              </label>
              <input
                id="email"
                className={styles.input}
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="nume@companie.md"
                autoComplete="email"
                required
              />
            </div>

            <div className={styles.field}>
              <label className={styles.label} htmlFor="password">
                Parolă
              </label>
              <input
                id="password"
                className={styles.input}
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder={isRegister ? `Minim ${MIN_PASSWORD_LENGTH} caractere` : '••••••••'}
                // Tells a password manager whether to offer to save a new one
                // or fill the existing one. Getting this wrong is a common way
                // to make managers unusable.
                autoComplete={isRegister ? 'new-password' : 'current-password'}
                aria-describedby={isRegister ? 'password-hint' : undefined}
                required
                {...(isRegister ? { minLength: MIN_PASSWORD_LENGTH } : {})}
              />
              {isRegister && (
                <span id="password-hint" className={styles.hint}>
                  Minim {MIN_PASSWORD_LENGTH} caractere.
                </span>
              )}
            </div>

            {error && (
              <p className={styles.error} role="alert">
                {error}
              </p>
            )}

            <button type="submit" className={styles.submit} disabled={submitting}>
              {submitting ? 'Se procesează…' : isRegister ? 'Creează cont' : 'Autentifică-te'}
            </button>
          </form>

          <p className={styles.switch}>
            {isRegister ? 'Ai deja un cont?' : 'Nu ai încă un cont?'}{' '}
            <button
              type="button"
              className={styles.linkButton}
              onClick={() => switchTo(isRegister ? 'login' : 'register')}
            >
              {isRegister ? 'Autentifică-te' : 'Creează unul'}
            </button>
          </p>
        </div>
      </main>
    </div>
  )
}

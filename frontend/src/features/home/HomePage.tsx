/**
 * Placeholder home screen.
 *
 * Phase 3's "you can register, log in, and see your own name". It shows who is
 * signed in and lets them sign out — enough to prove auth works end to end.
 *
 * Phase 4 replaces this with the real app shell and the catalog.
 */

import { useAuth } from '@/features/auth/AuthContext'
import { SystemStatus } from '@/features/health/SystemStatus'

import styles from './HomePage.module.css'

function initials(fullName: string): string {
  return fullName
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() ?? '')
    .join('')
}

export function HomePage() {
  const { user, logout } = useAuth()

  if (!user) return null

  return (
    <div className={styles.page}>
      <header className={styles.header}>
        <div>
          <p className={styles.brandMark}>CONTRACTE.MD</p>
          <p className={styles.brandSub}>Crowe Turcan Mikhailenko</p>
        </div>

        <div className={styles.userBox}>
          <span className={styles.avatar} aria-hidden="true">
            {initials(user.full_name)}
          </span>
          <div className={styles.userText}>
            <p className={styles.userName}>{user.full_name}</p>
            <p className={styles.userEmail}>{user.email}</p>
          </div>
          <button type="button" className={styles.logout} onClick={() => void logout()}>
            Ieși din cont
          </button>
        </div>
      </header>

      <main className={styles.main}>
        <p className={styles.phase}>Faza 3 — autentificare</p>
        <h1 className={styles.title}>Salut, {user.full_name.split(' ')[0]}.</h1>
        <p className={styles.text}>
          Ești autentificat. Catalogul de contracte apare în faza 4.
        </p>

        <SystemStatus />
      </main>
    </div>
  )
}

/**
 * The signed-in shell: sidebar plus header.
 *
 * Implements Sidebar.dc.html. On narrow screens the sidebar becomes a bottom
 * bar, as the prototype's media queries specified.
 *
 * Retires Sidebar.dc.html.
 */

import type { ReactNode } from 'react'
import { NavLink } from 'react-router-dom'

import { useAuth } from '@/features/auth/AuthContext'

import styles from './AppShell.module.css'

function initials(fullName: string): string {
  return fullName
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() ?? '')
    .join('')
}

const NAV = [
  {
    to: '/',
    label: 'Panou principal',
    icon: (
      <>
        <rect x="3" y="3" width="7" height="7" rx="1.5" />
        <rect x="14" y="3" width="7" height="7" rx="1.5" />
        <rect x="3" y="14" width="7" height="7" rx="1.5" />
        <rect x="14" y="14" width="7" height="7" rx="1.5" />
      </>
    ),
  },
  {
    to: '/documentele-mele',
    label: 'Documentele mele',
    icon: (
      <>
        <path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z" />
        <path d="M14 3v5h5" />
      </>
    ),
  },
  {
    to: '/cos',
    label: 'Coș',
    icon: (
      <>
        <circle cx="9" cy="20" r="1.4" />
        <circle cx="18" cy="20" r="1.4" />
        <path d="M2 3h3l2.4 12.4a2 2 0 0 0 2 1.6h8a2 2 0 0 0 2-1.6L22 7H6" />
      </>
    ),
  },
  {
    to: '/portofel',
    label: 'Portofel',
    icon: (
      <>
        <rect x="2" y="5" width="20" height="14" rx="2.5" />
        <line x1="2" y1="10" x2="22" y2="10" />
      </>
    ),
  },
  {
    to: '/setari',
    label: 'Setări',
    icon: (
      <>
        <circle cx="12" cy="12" r="3" />
        <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-2.82 1.17V21a2 2 0 1 1-4 0v-.09A1.65 1.65 0 0 0 8 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.6 15H4.5a2 2 0 1 1 0-4h.09A1.65 1.65 0 0 0 6 9.4l-.11-.11a2 2 0 1 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 11 6.6V6.5a2 2 0 1 1 4 0v.09a1.65 1.65 0 0 0 2.82 1.17l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 13.5V15Z" />
      </>
    ),
  },
]

interface Props {
  title: string
  subtitle?: string
  children: ReactNode
  /** Rendered on the right of the header — a search box, a button. */
  headerRight?: ReactNode
}

export function AppShell({ title, subtitle, children, headerRight }: Props) {
  const { user, logout } = useAuth()

  return (
    <div className={styles.shell}>
      <aside className={styles.sidebar}>
        <div className={styles.brand}>
          <p className={styles.brandMark}>CONTRACTE.MD</p>
          <p className={styles.brandSub}>Crowe Turcan Mikhailenko</p>
        </div>

        <nav className={styles.nav}>
          {NAV.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              // `end` on the root link only. Without it "/" matches every
              // route and every nav item lights up at once.
              end={item.to === '/'}
              className={({ isActive }) => (isActive ? styles.navItemOn : styles.navItem)}
            >
              <svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
                {item.icon}
              </svg>
              <span className={styles.navLabel}>{item.label}</span>
            </NavLink>
          ))}
        </nav>

        {user && (
          <div className={styles.foot}>
            <div className={styles.userBox}>
              <span className={styles.avatar} aria-hidden="true">
                {initials(user.full_name)}
              </span>
              <div className={styles.userText}>
                <p className={styles.userName}>{user.full_name}</p>
                <p className={styles.userEmail}>{user.email}</p>
              </div>
            </div>
            <button type="button" className={styles.logout} onClick={() => void logout()}>
              Ieși din cont
            </button>
          </div>
        )}
      </aside>

      <div className={styles.body}>
        <header className={styles.header}>
          <div>
            <h1 className={styles.title}>{title}</h1>
            {subtitle && <p className={styles.subtitle}>{subtitle}</p>}
          </div>
          {headerRight}
        </header>

        <main className={styles.main}>{children}</main>
      </div>
    </div>
  )
}

/**
 * The shell for pages a visitor can browse either signed in or signed out:
 * the catalog and a contract's detail.
 *
 * Signed in, they are part of the app and wear the sidebar (AppShell). Signed
 * out, they are the public shop and wear the marketing nav and footer
 * (PublicLayout). The page content is identical; only the chrome differs, so it
 * is chosen here once rather than branched inside every page.
 */

import type { ReactNode } from 'react'

import { useAuth } from '@/features/auth/AuthContext'

import { AppShell } from './AppShell'
import styles from './BrowseLayout.module.css'
import { PublicLayout } from './PublicLayout'

interface Props {
  title: string
  subtitle?: string
  children: ReactNode
  /** Rendered on the right of the header — only used by the signed-in shell. */
  headerRight?: ReactNode
}

export function BrowseLayout({ title, subtitle, headerRight, children }: Props) {
  const { user, loading } = useAuth()

  // Wait for the session check before committing to a chrome. Rendering the
  // public shell first and swapping to the sidebar a moment later would flash
  // the wrong layout on every load for a signed-in user. This mirrors
  // RequireAuth, which also renders nothing until the check settles.
  if (loading) return null

  if (user) {
    return (
      <AppShell title={title} subtitle={subtitle} headerRight={headerRight}>
        {children}
      </AppShell>
    )
  }

  return (
    <PublicLayout>
      <div className={styles.head}>
        <div className={styles.headInner}>
          <h1 className={styles.title}>{title}</h1>
          {subtitle && <p className={styles.subtitle}>{subtitle}</p>}
        </div>
      </div>
      <main className={styles.main}>{children}</main>
    </PublicLayout>
  )
}

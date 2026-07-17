/**
 * The public shell: sticky top nav and footer, no sidebar.
 *
 * Wraps the pages a signed-out visitor can see — the Landing page and, when
 * signed out, the catalog and contract detail (see BrowseLayout). The signed-in
 * app uses AppShell instead.
 *
 * Part of what Landing.dc.html specified; the marketing chrome lives here so the
 * Landing page itself is only content.
 */

import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'

import { useAuth } from '@/features/auth/AuthContext'

import styles from './PublicLayout.module.css'

export function PublicLayout({ children }: { children: ReactNode }) {
  const { user } = useAuth()

  return (
    <div className={styles.page}>
      <header className={styles.nav}>
        <div className={styles.navInner}>
          <Link to="/" className={styles.brand}>
            <span className={styles.brandMark}>CONTRACTUL.MD</span>
          </Link>

          <nav className={styles.links}>
            <Link to="/catalog" className={styles.link}>
              Contracte
            </Link>
          </nav>

          <div className={styles.actions}>
            {user ? (
              <Link to="/catalog" className={styles.cta}>
                Panoul meu
              </Link>
            ) : (
              <>
                <Link to="/autentificare" className={styles.signIn}>
                  Autentificare
                </Link>
                <Link to="/autentificare" className={styles.cta}>
                  Creează cont
                </Link>
              </>
            )}
          </div>
        </div>
      </header>

      {children}

      <footer className={styles.footer}>
        <div className={styles.footerGrid}>
          <div>
            <p className={styles.footBrand}>CONTRACTUL.MD</p>
            <p className={styles.footText}>
              Documente juridice conforme legislației Republicii Moldova, gata în câteva minute.
            </p>
          </div>

          <div>
            <p className={styles.footHead}>Produs</p>
            <div className={styles.footLinks}>
              <Link to="/catalog" className={styles.footLink}>
                Contracte
              </Link>
              <Link to="/portofel" className={styles.footLink}>
                Portofel
              </Link>
            </div>
          </div>

          <div>
            <p className={styles.footHead}>Contact</p>
            <div className={styles.footLinks}>
              <span className={styles.footMeta}>+373 79 027 317</span>
              <span className={styles.footMeta}>str. Alexei Șciusev 29, Chișinău</span>
            </div>
          </div>
        </div>

        <div className={styles.footBar}>
          <div className={styles.footBarInner}>
            © 2026 Contractul.md. Toate drepturile rezervate.
          </div>
        </div>
      </footer>
    </div>
  )
}

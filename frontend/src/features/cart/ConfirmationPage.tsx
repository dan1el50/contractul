/**
 * Confirmare — the post-checkout receipt.
 *
 * Implements Confirmare.dc.html. Retires Confirmare.dc.html.
 *
 * Honest about what has and has not happened yet:
 *
 * - The prototype says "Documentul tău este gata" and offers PDF/Word
 *   downloads. Generation is phase 7 (and waits on the real templates), so the
 *   payment is confirmed but the files are not ready — the page says exactly
 *   that instead of dangling buttons that do nothing.
 * - The prototype claims a "factură fiscală" was emailed. We issue none — that
 *   is what makes gap-tolerant order numbers safe — so the claim is gone.
 * - Payment was from the wallet, not a card, and the receipt says so.
 */

import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'

import { AppShell } from '@/app/layouts/AppShell'
import { ApiError } from '@/lib/api-client'

import { fetchOrder, type Order } from './api'
import styles from './ConfirmationPage.module.css'

function formatDate(iso: string): string {
  return new Date(iso).toLocaleString('ro-MD', {
    day: 'numeric',
    month: 'long',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export function ConfirmationPage() {
  const { orderId = '' } = useParams()
  const [order, setOrder] = useState<Order | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    setError(null)
    setOrder(null)
    fetchOrder(orderId)
      .then((o) => !cancelled && setOrder(o))
      .catch((caught: unknown) => {
        if (cancelled) return
        setError(
          caught instanceof ApiError && caught.status === 404
            ? 'Comanda nu a fost găsită.'
            : 'Nu am putut încărca comanda.',
        )
      })
    return () => {
      cancelled = true
    }
  }, [orderId])

  if (error) {
    return (
      <AppShell title="Comandă">
        <p className={styles.error} role="alert">
          {error}
        </p>
        <Link to="/catalog" className={styles.back}>
          ← Înapoi la catalog
        </Link>
      </AppShell>
    )
  }

  if (!order) {
    return (
      <AppShell title="Comandă">
        <p className={styles.loading}>Se încarcă…</p>
      </AppShell>
    )
  }

  return (
    <AppShell title="Comandă confirmată">
      <div className={styles.wrap}>
        <div className={styles.hero}>
          <div className={styles.check} aria-hidden="true">
            <svg width="38" height="38" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="2.6">
              <path d="M20 6 9 17l-5-5" />
            </svg>
          </div>
          <p className={styles.kicker}>Plată confirmată</p>
          <h1 className={styles.heroTitle}>Comanda ta este confirmată</h1>
          <p className={styles.heroText}>
            Plata a fost efectuată din portofel. Contractele vor apărea în „Documentele mele"
            imediat ce sunt generate.
          </p>
        </div>

        <div className={styles.body}>
          <dl className={styles.receipt}>
            <div className={styles.row}>
              <dt>Comandă</dt>
              <dd className={styles.strong}>#{order.number}</dd>
            </div>
            <div className={styles.row}>
              <dt>Data</dt>
              <dd>{formatDate(order.paid_at ?? order.created_at)}</dd>
            </div>
            <div className={styles.row}>
              <dt>Metodă</dt>
              <dd>Portofel Contracte</dd>
            </div>
            <div className={styles.row}>
              <dt>Sumă achitată</dt>
              <dd className={styles.strong}>{order.total_mdl} MDL</dd>
            </div>
          </dl>

          <ul className={styles.items}>
            {order.items.map((item) => (
              <li key={item.template_id} className={styles.item}>
                <span>{item.name_snapshot}</span>
                <span className={styles.itemPrice}>{item.unit_price_mdl} MDL</span>
              </li>
            ))}
          </ul>

          <div className={styles.pending}>
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#003f9f" strokeWidth="1.9" aria-hidden="true">
              <circle cx="12" cy="12" r="10" />
              <path d="M12 8v4l3 2" />
            </svg>
            <p>
              Descărcarea în PDF și Word editabil va fi disponibilă din „Documentele mele" în
              curând.
            </p>
          </div>

          <div className={styles.actions}>
            <Link to="/catalog" className={styles.link}>
              ← Înapoi la catalog
            </Link>
          </div>
        </div>
      </div>
    </AppShell>
  )
}

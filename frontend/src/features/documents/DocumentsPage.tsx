/**
 * Documentele mele — the contracts a user has purchased.
 *
 * Implements Documentele Mele.dc.html, honestly for where the product is:
 * every paid order line is a document the user owns, but the PDF/Word files are
 * generated in phase 7 (which waits on the real templates). So each row lists a
 * purchased contract with a "being prepared" state and the download disabled,
 * exactly as the confirmation screen promises. When phase 7 lands, the state
 * flips to ready and the button downloads the file.
 *
 * The prototype's Dashboard Admin.dc.html download menu remains the spec for
 * that interaction, so it is not retired yet.
 */

import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'

import { AppShell } from '@/app/layouts/AppShell'
import { ApiError } from '@/lib/api-client'

import { fetchMyOrders, type PurchaseOrder } from './api'
import styles from './DocumentsPage.module.css'

interface DocumentRow {
  key: string
  name: string
  orderNumber: string
  date: string
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString('ro-MD', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  })
}

/** Flatten paid orders into one row per purchased contract, newest first. */
function toDocuments(orders: PurchaseOrder[]): DocumentRow[] {
  return orders
    .filter((order) => order.status === 'paid')
    .flatMap((order) =>
      order.items.map((item) => ({
        key: `${order.id}:${item.template_id}`,
        name: item.name_snapshot,
        orderNumber: order.number,
        date: formatDate(order.paid_at ?? order.created_at),
      })),
    )
}

export function DocumentsPage() {
  const [documents, setDocuments] = useState<DocumentRow[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    fetchMyOrders()
      .then((orders) => !cancelled && setDocuments(toDocuments(orders)))
      .catch((caught: unknown) => {
        if (cancelled) return
        setError(
          caught instanceof ApiError ? caught.message : 'Nu am putut încărca documentele.',
        )
      })
    return () => {
      cancelled = true
    }
  }, [])

  return (
    <AppShell title="Documentele mele" subtitle="Contractele pe care le-ai cumpărat">
      {error && (
        <p className={styles.error} role="alert">
          {error}
        </p>
      )}

      {documents !== null && documents.length === 0 && !error && (
        <div className={styles.empty}>
          <span className={styles.emptyIcon} aria-hidden="true">
            <svg width="30" height="30" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6">
              <path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z" />
              <path d="M14 3v5h5" />
            </svg>
          </span>
          <h2 className={styles.emptyTitle}>Nu ai încă niciun document</h2>
          <p className={styles.emptyText}>
            Contractele pe care le cumperi apar aici, gata de descărcat.
          </p>
          <Link to="/catalog" className={styles.emptyCta}>
            Vezi contractele
          </Link>
        </div>
      )}

      {documents !== null && documents.length > 0 && (
        <div className={styles.card}>
          <table className={styles.table}>
            <thead>
              <tr>
                <th>Document</th>
                <th>Comandă</th>
                <th>Data</th>
                <th className={styles.right}>Status</th>
                <th className={styles.right}>Acțiune</th>
              </tr>
            </thead>
            <tbody>
              {documents.map((doc) => (
                <tr key={doc.key}>
                  <td>
                    <div className={styles.docCell}>
                      <span className={styles.docIcon} aria-hidden="true">
                        <svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
                          <path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z" />
                          <path d="M14 3v5h5" />
                        </svg>
                      </span>
                      <span className={styles.docName}>{doc.name}</span>
                    </div>
                  </td>
                  <td className={styles.mono}>{doc.orderNumber}</td>
                  <td className={styles.date}>{doc.date}</td>
                  <td className={styles.right}>
                    <span className={styles.statusPending}>În pregătire</span>
                  </td>
                  <td className={styles.right}>
                    <button
                      type="button"
                      className={styles.download}
                      disabled
                      title="Descărcarea va fi disponibilă în curând"
                    >
                      Descarcă
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className={styles.footnote}>
            Descărcarea în PDF și Word editabil va fi disponibilă în curând.
          </p>
        </div>
      )}
    </AppShell>
  )
}

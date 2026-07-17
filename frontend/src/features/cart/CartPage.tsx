/**
 * Coș — the cart and checkout.
 *
 * Implements Cos.dc.html. Retires Cos.dc.html.
 *
 * One departure from the prototype: payment is from the wallet only. The
 * prototype offers a card option too, but paying a card directly at checkout
 * needs the real acquirer (phase 10); until then the wallet — which the mock
 * top-up funds — is the one funded path. The card option is left out rather
 * than shown broken.
 */

import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'

import { AppShell } from '@/app/layouts/AppShell'
import { useCart } from '@/features/cart/CartContext'
import { ApiError } from '@/lib/api-client'

import { checkout, fetchWalletBalance } from './api'
import styles from './CartPage.module.css'

export function CartPage() {
  const { cart, remove, refresh } = useCart()
  const navigate = useNavigate()

  const [balance, setBalance] = useState<{ balance_bani: number; balance_mdl: string } | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    void refresh().catch(() => setError('Nu am putut încărca coșul.'))
    void fetchWalletBalance().then(setBalance).catch(() => setBalance(null))
  }, [refresh])

  const total = cart?.total_bani ?? 0
  const lowBalance = balance !== null && balance.balance_bani < total
  const empty = !cart || cart.item_count === 0

  async function handleRemove(templateId: string) {
    setError(null)
    try {
      await remove(templateId)
    } catch {
      setError('Nu am putut elimina contractul.')
    }
  }

  async function handleCheckout() {
    setBusy(true)
    setError(null)
    try {
      const order = await checkout()
      // The cart is now empty server-side; mirror that before leaving.
      await refresh()
      navigate(`/comanda/${order.id}`, { replace: true })
    } catch (caught) {
      if (caught instanceof ApiError && caught.status === 402) {
        setError('Sold insuficient. Alimentează portofelul și încearcă din nou.')
        void fetchWalletBalance().then(setBalance).catch(() => {})
      } else {
        setError(caught instanceof ApiError ? caught.message : 'Plata nu a putut fi finalizată.')
      }
    } finally {
      setBusy(false)
    }
  }

  return (
    <AppShell title="Coș" subtitle="Verifică și plătește contractele selectate">
      <div className={styles.layout}>
        <div className={styles.left}>
          <section className={styles.card}>
            <div className={styles.cardHead}>
              <h2 className={styles.cardTitle}>Contracte selectate</h2>
              <span className={styles.count}>{cart?.item_count ?? 0} articole</span>
            </div>

            {empty ? (
              <p className={styles.empty}>
                Coșul este gol. <Link to="/catalog">Vezi contractele</Link> și adaugă unul.
              </p>
            ) : (
              <>
                <ul className={styles.items}>
                  {cart.items.map((item) => (
                    <li key={item.template_id} className={styles.item}>
                      <span className={styles.itemIcon} aria-hidden="true">
                        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7">
                          <path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z" />
                          <path d="M14 3v5h5" />
                        </svg>
                      </span>
                      <div className={styles.itemText}>
                        <p className={styles.itemName}>{item.name}</p>
                        <p className={styles.itemMeta}>{item.category_name} · PDF + Word</p>
                      </div>
                      <span className={styles.itemPrice}>{item.price_mdl} MDL</span>
                      <button
                        type="button"
                        className={styles.remove}
                        aria-label={`Elimină ${item.name}`}
                        onClick={() => void handleRemove(item.template_id)}
                      >
                        <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.9">
                          <polyline points="3 6 5 6 21 6" />
                          <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
                        </svg>
                      </button>
                    </li>
                  ))}
                </ul>
                <Link to="/catalog" className={styles.addMore}>
                  + Adaugă alt contract
                </Link>
              </>
            )}
          </section>

          {!empty && (
            <section className={styles.card}>
              <h2 className={styles.cardTitle}>Metodă de plată</h2>
              <div className={styles.walletBox}>
                <span className={styles.walletIcon} aria-hidden="true">
                  <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="var(--color-amber)" strokeWidth="1.9">
                    <path d="M21 12V7H5a2 2 0 0 1 0-4h14v4" />
                    <path d="M3 5v14a2 2 0 0 0 2 2h16v-5" />
                    <path d="M18 12a2 2 0 0 0 0 4h4v-4Z" />
                  </svg>
                </span>
                <div className={styles.walletText}>
                  <p className={styles.walletName}>Portofel Contracte</p>
                  <p className={styles.walletBalance}>
                    Sold disponibil: <strong>{balance?.balance_mdl ?? '—'} MDL</strong>
                  </p>
                </div>
              </div>

              {lowBalance && (
                <div className={styles.warning} role="alert">
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#b26a00" strokeWidth="2" aria-hidden="true">
                    <circle cx="12" cy="12" r="10" />
                    <line x1="12" y1="8" x2="12" y2="12" />
                    <line x1="12" y1="16" x2="12.01" y2="16" />
                  </svg>
                  <p>
                    Sold insuficient pentru această comandă.{' '}
                    <Link to="/portofel">Alimentează portofelul</Link>.
                  </p>
                </div>
              )}
            </section>
          )}
        </div>

        {!empty && (
          <aside className={styles.summary}>
            <h2 className={styles.cardTitle}>Sumar comandă</h2>
            <div className={styles.summaryRows}>
              <div className={styles.summaryRow}>
                <span>Subtotal ({cart.item_count})</span>
                <strong>{cart.total_mdl} MDL</strong>
              </div>
              <div className={styles.summaryRow}>
                <span>TVA (20%)</span>
                <strong>inclus</strong>
              </div>
              <div className={styles.summaryRow}>
                <span>Format PDF + Word</span>
                <strong className={styles.free}>gratuit</strong>
              </div>
            </div>
            <div className={styles.total}>
              <span>Total de plată</span>
              <strong>{cart.total_mdl} MDL</strong>
            </div>

            {error && (
              <p className={styles.error} role="alert">
                {error}
              </p>
            )}

            <button
              type="button"
              className={styles.payButton}
              onClick={() => void handleCheckout()}
              disabled={busy || lowBalance}
            >
              {busy ? 'Se procesează…' : 'Plătește din portofel'}
            </button>
            <p className={styles.note}>
              După plată, contractele se deblochează în „Documentele mele".
            </p>
          </aside>
        )}
      </div>
    </AppShell>
  )
}

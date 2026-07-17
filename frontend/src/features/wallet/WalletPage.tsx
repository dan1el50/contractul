/**
 * Portofel — balance, top-up, and transaction history.
 *
 * Implements Portofel.dc.html. Retires Portofel.dc.html.
 *
 * The prototype advertised "bonus până la 20% la alimentare". There is no
 * bonus: nobody has specified one, and inventing a discount scheme in the UI
 * would be inventing a business rule. Ask before restoring that copy.
 */

import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'

import { AppShell } from '@/app/layouts/AppShell'
import { ApiError } from '@/lib/api-client'

import {
  fetchBalance,
  fetchCards,
  fetchTransactions,
  topUp,
  type Balance,
  type Card,
  type Transaction,
} from './api'
import styles from './WalletPage.module.css'

/** Bani. Mirrors MIN_TOPUP_BANI / MAX_TOPUP_BANI on the server. */
const PRESETS = [50000, 100000, 200000, 300000, 500000, 1000000]

function formatMdl(bani: number): string {
  return `${Math.floor(bani / 100)}`.replace(/\B(?=(\d{3})+(?!\d))/g, ' ')
}

export function WalletPage() {
  const [balance, setBalance] = useState<Balance | null>(null)
  const [cards, setCards] = useState<Card[]>([])
  const [transactions, setTransactions] = useState<Transaction[]>([])
  const [selected, setSelected] = useState<number>(200000)
  const [cardId, setCardId] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const load = useCallback(async () => {
    const [b, c, t] = await Promise.all([fetchBalance(), fetchCards(), fetchTransactions()])
    setBalance(b)
    setCards(c)
    setTransactions(t)
    setCardId((current) => current ?? c.find((card) => card.is_default)?.id ?? c[0]?.id ?? null)
  }, [])

  useEffect(() => {
    void load().catch(() => setError('Nu am putut încărca portofelul.'))
  }, [load])

  async function handleTopUp() {
    if (!cardId) return
    setBusy(true)
    setError(null)

    try {
      await topUp(cardId, selected)
      // Refetch rather than patching local state. The balance is derived from
      // the ledger on the server; recomputing it here would be a second,
      // divergent implementation of the same rule.
      await load()
    } catch (caught) {
      setError(
        caught instanceof ApiError ? caught.message : 'Alimentarea nu a putut fi finalizată.',
      )
    } finally {
      setBusy(false)
    }
  }

  const newBalance = (balance?.balance_bani ?? 0) + selected

  return (
    <AppShell title="Portofel" subtitle="Alimentează contul o dată și cumpără contracte instant">
      <div className={styles.layout}>
        <div className={styles.left}>
          <section className={styles.balanceCard}>
            <p className={styles.balanceLabel}>Sold disponibil</p>
            <p className={styles.balanceValue}>
              {balance?.balance_mdl ?? '—'} <span className={styles.balanceUnit}>MDL</span>
            </p>
          </section>

          <section className={styles.card}>
            <h2 className={styles.cardTitle}>Alege suma de alimentare</h2>
            <div className={styles.presets}>
              {PRESETS.map((amount) => (
                <button
                  key={amount}
                  type="button"
                  className={selected === amount ? styles.presetOn : styles.preset}
                  onClick={() => setSelected(amount)}
                >
                  <span className={styles.presetAmount}>{formatMdl(amount)}</span>
                  <span className={styles.presetUnit}>MDL</span>
                </button>
              ))}
            </div>
          </section>

          <section className={styles.card}>
            <h2 className={styles.cardTitle}>Metodă de plată</h2>

            {cards.length === 0 ? (
              <p className={styles.noCards}>
                Nu ai niciun card salvat.{' '}
                <Link to="/portofel/card-nou">Adaugă un card</Link> pentru a alimenta contul.
              </p>
            ) : (
              <div className={styles.cardList}>
                {cards.map((card) => (
                  <label
                    key={card.id}
                    className={cardId === card.id ? styles.cardOptionOn : styles.cardOption}
                  >
                    <input
                      type="radio"
                      name="card"
                      className={styles.radio}
                      checked={cardId === card.id}
                      onChange={() => setCardId(card.id)}
                    />
                    <span className={styles.cardChip} aria-hidden="true" />
                    <span className={styles.cardInfo}>
                      <span className={styles.cardBrand}>
                        {card.brand.toUpperCase()} •••• {card.last4}
                      </span>
                      <span className={styles.cardExp}>
                        Expiră {String(card.exp_month).padStart(2, '0')}/
                        {String(card.exp_year).slice(-2)}
                      </span>
                    </span>
                  </label>
                ))}
              </div>
            )}

            <Link to="/portofel/card-nou" className={styles.addCard}>
              + Adaugă un card nou
            </Link>
          </section>
        </div>

        <aside className={styles.summary}>
          <h2 className={styles.cardTitle}>Rezumat alimentare</h2>

          <div className={styles.summaryRows}>
            <div className={styles.summaryRow}>
              <span>Sumă alimentată</span>
              <strong>{formatMdl(selected)} MDL</strong>
            </div>
            <div className={styles.summaryRow}>
              <span>Sold actual</span>
              <strong>{balance?.balance_mdl ?? '—'} MDL</strong>
            </div>
          </div>

          <div className={styles.newBalance}>
            <span>Sold nou</span>
            <strong>{formatMdl(newBalance)} MDL</strong>
          </div>

          {error && (
            <p className={styles.error} role="alert">
              {error}
            </p>
          )}

          <button
            type="button"
            className={styles.topUpButton}
            onClick={() => void handleTopUp()}
            disabled={busy || !cardId}
          >
            {busy ? 'Se procesează…' : 'Alimentează contul'}
          </button>
          {!cardId && <p className={styles.hint}>Adaugă un card pentru a continua.</p>}
        </aside>
      </div>

      <section className={styles.history}>
        <h2 className={styles.cardTitle}>Istoric tranzacții</h2>

        {transactions.length === 0 ? (
          <p className={styles.empty}>Nicio tranzacție încă.</p>
        ) : (
          <ul className={styles.txList}>
            {transactions.map((transaction) => (
              <li key={transaction.id} className={styles.tx}>
                <span
                  className={transaction.amount_bani > 0 ? styles.txIconIn : styles.txIconOut}
                  aria-hidden="true"
                />
                <div className={styles.txText}>
                  <p className={styles.txTitle}>{transaction.description}</p>
                  <p className={styles.txDate}>
                    {new Date(transaction.created_at).toLocaleDateString('ro-MD', {
                      day: 'numeric',
                      month: 'short',
                      year: 'numeric',
                    })}
                  </p>
                </div>
                <span
                  className={transaction.amount_bani > 0 ? styles.txAmountIn : styles.txAmountOut}
                >
                  {transaction.amount_mdl} MDL
                </span>
              </li>
            ))}
          </ul>
        )}
      </section>
    </AppShell>
  )
}

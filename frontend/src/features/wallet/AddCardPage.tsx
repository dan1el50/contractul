/**
 * Adaugă Card — a live card preview and a save form.
 *
 * Implements Adauga Card.dc.html. Retires Adauga Card.dc.html.
 *
 * ⚠ **This form posts card details to our own server, and that is a
 * development-only arrangement.** A real acquirer supplies a hosted field or an
 * iframe, and the number goes straight from the customer to them — our backend
 * never sees it, which is what keeps this system out of PCI-DSS scope.
 *
 * It works this way because the mock provider has no hosted field to embed.
 * When a real provider lands, this page is not rewritten to call it: the whole
 * server-side path is deleted and replaced by their embed.
 */

import { useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'

import { AppShell } from '@/app/layouts/AppShell'
import { ApiError } from '@/lib/api-client'

import { addCard } from './api'
import styles from './AddCardPage.module.css'

function formatNumber(raw: string): string {
  const digits = raw.replace(/\D/g, '').slice(0, 16)
  return digits.replace(/(.{4})/g, '$1 ').trim()
}

function formatExpiry(raw: string): string {
  const digits = raw.replace(/\D/g, '').slice(0, 4)
  if (digits.length <= 2) return digits
  return `${digits.slice(0, 2)} / ${digits.slice(2)}`
}

function brandOf(number: string): string {
  const digits = number.replace(/\D/g, '')
  if (digits.startsWith('4')) return 'VISA'
  if (/^5[1-5]/.test(digits)) return 'Mastercard'
  if (/^3[47]/.test(digits)) return 'AMEX'
  return 'CARD'
}

export function AddCardPage() {
  const navigate = useNavigate()

  const [number, setNumber] = useState('')
  const [expiry, setExpiry] = useState('')
  const [cvv, setCvv] = useState('')
  const [makeDefault, setMakeDefault] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const digits = number.replace(/\D/g, '')
  const expDigits = expiry.replace(/\D/g, '')

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    setError(null)

    if (expDigits.length !== 4) {
      setError('Introdu data expirării în formatul LL / AA.')
      return
    }

    setBusy(true)
    try {
      await addCard({
        number: digits,
        exp_month: Number(expDigits.slice(0, 2)),
        // "28" -> 2028. Two-digit years are ambiguous forever; cards do not
        // expire in the 1900s, so the century is safe to assume here.
        exp_year: 2000 + Number(expDigits.slice(2)),
        cvv,
        make_default: makeDefault,
      })
      navigate('/portofel', { replace: true })
    } catch (caught) {
      setError(
        caught instanceof ApiError ? caught.message : 'Cardul nu a putut fi salvat.',
      )
    } finally {
      setBusy(false)
    }
  }

  return (
    <AppShell title="Adaugă un card" subtitle="Plăți securizate, procesate în platformă">
      <div className={styles.wrap}>
        <div className={styles.preview} aria-hidden="true">
          <div className={styles.chip} />
          <p className={styles.previewBrand}>{brandOf(number)}</p>
          <p className={styles.previewNumber}>{number || '•••• •••• •••• ••••'}</p>
          <div className={styles.previewFoot}>
            <span>Expiră</span>
            <span>{expiry || 'LL / AA'}</span>
          </div>
        </div>

        <form onSubmit={handleSubmit} className={styles.form} noValidate>
          <div className={styles.field}>
            <label className={styles.label} htmlFor="number">
              Numărul cardului
            </label>
            <input
              id="number"
              className={styles.input}
              value={number}
              onChange={(e) => setNumber(formatNumber(e.target.value))}
              placeholder="4242 4242 4242 4242"
              inputMode="numeric"
              autoComplete="cc-number"
              required
            />
          </div>

          <div className={styles.row}>
            <div className={styles.field}>
              <label className={styles.label} htmlFor="expiry">
                Expiră
              </label>
              <input
                id="expiry"
                className={styles.input}
                value={expiry}
                onChange={(e) => setExpiry(formatExpiry(e.target.value))}
                placeholder="09 / 28"
                inputMode="numeric"
                autoComplete="cc-exp"
                required
              />
            </div>

            <div className={styles.field}>
              <label className={styles.label} htmlFor="cvv">
                CVV
              </label>
              <input
                id="cvv"
                className={styles.input}
                type="password"
                value={cvv}
                onChange={(e) => setCvv(e.target.value.replace(/\D/g, '').slice(0, 4))}
                placeholder="•••"
                inputMode="numeric"
                autoComplete="cc-csc"
                required
              />
            </div>
          </div>

          <label className={styles.checkboxRow}>
            <input
              type="checkbox"
              checked={makeDefault}
              onChange={(e) => setMakeDefault(e.target.checked)}
            />
            Setează ca principal
          </label>

          {error && (
            <p className={styles.error} role="alert">
              {error}
            </p>
          )}

          <div className={styles.actions}>
            <button type="submit" className={styles.save} disabled={busy}>
              {busy ? 'Se salvează…' : 'Salvează cardul'}
            </button>
            <Link to="/portofel" className={styles.cancel}>
              Anulează
            </Link>
          </div>

          <p className={styles.testCards}>
            Carduri de test: <code>4242 4242 4242 4242</code> reușește,{' '}
            <code>4000 0000 0000 0002</code> este refuzat.
          </p>
        </form>
      </div>
    </AppShell>
  )
}

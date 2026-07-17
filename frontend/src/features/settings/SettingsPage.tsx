/**
 * Setări — profile, company, payment methods, and password.
 *
 * Implements Setari.dc.html. Retires Setari.dc.html.
 *
 * Two tabs from the prototype are left out on purpose: "Notificări" and
 * "Limbă și regiune" have no backend — there is nothing to send and nothing to
 * store — and a panel of switches that change nothing is worse than no panel.
 * They return when a feature stands behind them.
 */

import { useEffect, useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'

import { AppShell } from '@/app/layouts/AppShell'
import { useAuth } from '@/features/auth/AuthContext'
import { ApiError } from '@/lib/api-client'

import {
  changePassword,
  fetchCards,
  fetchCompany,
  saveCompany,
  updateProfile,
  type Company,
  type SavedCard,
} from './api'
import styles from './SettingsPage.module.css'

type Tab = 'profile' | 'company' | 'billing' | 'security'

const TABS: { key: Tab; label: string }[] = [
  { key: 'profile', label: 'Profil' },
  { key: 'company', label: 'Companie' },
  { key: 'billing', label: 'Metode de plată' },
  { key: 'security', label: 'Securitate' },
]

const MIN_PASSWORD_LENGTH = 10

export function SettingsPage() {
  const [tab, setTab] = useState<Tab>('profile')

  return (
    <AppShell title="Setări" subtitle="Gestionează contul, compania și securitatea">
      <div className={styles.layout}>
        <nav className={styles.tabs}>
          {TABS.map((t) => (
            <button
              key={t.key}
              type="button"
              className={tab === t.key ? styles.tabOn : styles.tab}
              onClick={() => setTab(t.key)}
            >
              {t.label}
            </button>
          ))}
        </nav>

        <div className={styles.panel}>
          {tab === 'profile' && <ProfileTab />}
          {tab === 'company' && <CompanyTab />}
          {tab === 'billing' && <BillingTab />}
          {tab === 'security' && <SecurityTab />}
        </div>
      </div>
    </AppShell>
  )
}

function Feedback({ ok, error }: { ok: string | null; error: string | null }) {
  if (error)
    return (
      <p className={styles.error} role="alert">
        {error}
      </p>
    )
  if (ok)
    return (
      <p className={styles.ok} role="status">
        {ok}
      </p>
    )
  return null
}

function ProfileTab() {
  const { user, refresh } = useAuth()
  const [fullName, setFullName] = useState(user?.full_name ?? '')
  const [phone, setPhone] = useState(user?.phone ?? '')
  const [ok, setOk] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    setOk(null)
    setError(null)
    setBusy(true)
    try {
      await updateProfile({ full_name: fullName, phone: phone.trim() || null })
      await refresh()
      setOk('Profilul a fost actualizat.')
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : 'Nu am putut salva profilul.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <form className={styles.section} onSubmit={handleSubmit}>
      <h2 className={styles.sectionTitle}>Profil utilizator</h2>
      <div className={styles.field}>
        <label className={styles.label} htmlFor="full_name">
          Nume complet
        </label>
        <input
          id="full_name"
          className={styles.input}
          value={fullName}
          onChange={(e) => setFullName(e.target.value)}
          minLength={2}
          required
        />
      </div>
      <div className={styles.field}>
        <label className={styles.label} htmlFor="email">
          Email
        </label>
        <input id="email" className={styles.input} value={user?.email ?? ''} disabled />
        <span className={styles.hint}>Adresa de email nu poate fi schimbată aici.</span>
      </div>
      <div className={styles.field}>
        <label className={styles.label} htmlFor="phone">
          Telefon
        </label>
        <input
          id="phone"
          className={styles.input}
          value={phone}
          onChange={(e) => setPhone(e.target.value)}
          placeholder="+373 79 000 000"
        />
      </div>

      <Feedback ok={ok} error={error} />
      <button type="submit" className={styles.save} disabled={busy}>
        {busy ? 'Se salvează…' : 'Salvează modificările'}
      </button>
    </form>
  )
}

function CompanyTab() {
  const [company, setCompany] = useState<Company | null>(null)
  const [form, setForm] = useState<{
    name: string
    idno: string
    legal_address: string
    iban: string
    bank_name: string
  }>({ name: '', idno: '', legal_address: '', iban: '', bank_name: '' })
  const [ok, setOk] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    fetchCompany()
      .then((c) => {
        setCompany(c)
        if (c)
          setForm({
            name: c.name,
            idno: c.idno,
            legal_address: c.legal_address ?? '',
            iban: c.iban ?? '',
            bank_name: c.bank_name ?? '',
          })
      })
      .catch(() => {})
  }, [])

  function set<K extends keyof typeof form>(key: K, value: string) {
    setForm((f) => ({ ...f, [key]: value }))
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    setOk(null)
    setError(null)
    setBusy(true)
    try {
      const saved = await saveCompany({
        name: form.name,
        idno: form.idno,
        legal_address: form.legal_address.trim() || null,
        iban: form.iban.trim() || null,
        bank_name: form.bank_name.trim() || null,
      })
      setCompany(saved)
      setOk('Datele companiei au fost salvate.')
    } catch (caught) {
      setError(
        caught instanceof ApiError && caught.status === 422
          ? 'Verifică datele: IDNO trebuie să aibă exact 13 cifre.'
          : 'Nu am putut salva datele companiei.',
      )
    } finally {
      setBusy(false)
    }
  }

  return (
    <form className={styles.section} onSubmit={handleSubmit}>
      <h2 className={styles.sectionTitle}>Date companie</h2>
      <p className={styles.sectionLead}>
        Opțional — completează dacă achiziționezi în numele unei companii.
      </p>
      <div className={styles.field}>
        <label className={styles.label} htmlFor="c_name">
          Denumire
        </label>
        <input
          id="c_name"
          className={styles.input}
          value={form.name}
          onChange={(e) => set('name', e.target.value)}
          placeholder='SRL "NordConstruct"'
          required
        />
      </div>
      <div className={styles.grid2}>
        <div className={styles.field}>
          <label className={styles.label} htmlFor="c_idno">
            IDNO
          </label>
          <input
            id="c_idno"
            className={styles.input}
            value={form.idno}
            onChange={(e) => set('idno', e.target.value)}
            placeholder="13 cifre"
            inputMode="numeric"
            pattern="\d{13}"
            required
          />
        </div>
        <div className={styles.field}>
          <label className={styles.label} htmlFor="c_bank">
            Bancă
          </label>
          <input
            id="c_bank"
            className={styles.input}
            value={form.bank_name}
            onChange={(e) => set('bank_name', e.target.value)}
            placeholder="Victoriabank"
          />
        </div>
      </div>
      <div className={styles.field}>
        <label className={styles.label} htmlFor="c_iban">
          IBAN
        </label>
        <input
          id="c_iban"
          className={styles.input}
          value={form.iban}
          onChange={(e) => set('iban', e.target.value)}
          placeholder="MD24 AG00 0225 1000 1310 4168"
        />
      </div>
      <div className={styles.field}>
        <label className={styles.label} htmlFor="c_addr">
          Adresă juridică
        </label>
        <input
          id="c_addr"
          className={styles.input}
          value={form.legal_address}
          onChange={(e) => set('legal_address', e.target.value)}
          placeholder="str. Alexei Șciusev 29, Chișinău"
        />
      </div>

      <Feedback ok={ok} error={error} />
      <button type="submit" className={styles.save} disabled={busy}>
        {busy ? 'Se salvează…' : company ? 'Actualizează datele' : 'Salvează datele'}
      </button>
    </form>
  )
}

function BillingTab() {
  const [cards, setCards] = useState<SavedCard[]>([])
  const [loaded, setLoaded] = useState(false)

  useEffect(() => {
    fetchCards()
      .then(setCards)
      .catch(() => {})
      .finally(() => setLoaded(true))
  }, [])

  return (
    <div className={styles.section}>
      <div className={styles.sectionHead}>
        <h2 className={styles.sectionTitle}>Metode de plată</h2>
        <Link to="/portofel/card-nou" className={styles.addCard}>
          + Adaugă card
        </Link>
      </div>

      {loaded && cards.length === 0 ? (
        <p className={styles.sectionLead}>Nu ai niciun card salvat.</p>
      ) : (
        <ul className={styles.cards}>
          {cards.map((card) => (
            <li key={card.id} className={styles.cardRow}>
              <span className={styles.cardChip} aria-hidden="true" />
              <span className={styles.cardInfo}>
                <strong>
                  {card.brand.toUpperCase()} •••• {card.last4}
                </strong>
                <span className={styles.cardExp}>
                  Expiră {String(card.exp_month).padStart(2, '0')}/{String(card.exp_year).slice(-2)}
                </span>
              </span>
              {card.is_default && <span className={styles.defaultTag}>Implicit</span>}
            </li>
          ))}
        </ul>
      )}

      <p className={styles.hint}>
        Gestionează cardurile și soldul în <Link to="/portofel">Portofel</Link>.
      </p>
    </div>
  )
}

function SecurityTab() {
  const [current, setCurrent] = useState('')
  const [next, setNext] = useState('')
  const [ok, setOk] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    setOk(null)
    setError(null)
    setBusy(true)
    try {
      await changePassword({ current_password: current, new_password: next })
      setCurrent('')
      setNext('')
      setOk('Parola a fost schimbată. Celelalte sesiuni au fost închise.')
    } catch (caught) {
      setError(
        caught instanceof ApiError && caught.status === 400
          ? 'Parola actuală este incorectă.'
          : caught instanceof ApiError && caught.status === 422
            ? `Parola nouă trebuie să aibă minim ${MIN_PASSWORD_LENGTH} caractere.`
            : 'Nu am putut schimba parola.',
      )
    } finally {
      setBusy(false)
    }
  }

  return (
    <form className={styles.section} onSubmit={handleSubmit}>
      <h2 className={styles.sectionTitle}>Schimbă parola</h2>
      <p className={styles.sectionLead}>
        După schimbare, vei rămâne conectat pe acest dispozitiv; celelalte sesiuni se închid.
      </p>
      <div className={styles.field}>
        <label className={styles.label} htmlFor="p_current">
          Parola actuală
        </label>
        <input
          id="p_current"
          className={styles.input}
          type="password"
          value={current}
          onChange={(e) => setCurrent(e.target.value)}
          autoComplete="current-password"
          required
        />
      </div>
      <div className={styles.field}>
        <label className={styles.label} htmlFor="p_new">
          Parola nouă
        </label>
        <input
          id="p_new"
          className={styles.input}
          type="password"
          value={next}
          onChange={(e) => setNext(e.target.value)}
          autoComplete="new-password"
          minLength={MIN_PASSWORD_LENGTH}
          required
        />
        <span className={styles.hint}>Minim {MIN_PASSWORD_LENGTH} caractere.</span>
      </div>

      <Feedback ok={ok} error={error} />
      <button type="submit" className={styles.save} disabled={busy}>
        {busy ? 'Se schimbă…' : 'Schimbă parola'}
      </button>
    </form>
  )
}

/**
 * Dashboard Admin — KPIs, monthly revenue, recent orders, template management.
 *
 * Implements Dashboard Admin.dc.html. Retires Dashboard Admin.dc.html.
 *
 * The prototype's "De procesat" approval queue is dropped: our checkout
 * completes a purchase atomically, so there is nothing awaiting manual approval.
 * The revenue chart is drawn as inline SVG — no chart library, so the page stays
 * self-contained.
 */

import { useEffect, useState, type FormEvent } from 'react'

import { AppShell } from '@/app/layouts/AppShell'
import { ApiError } from '@/lib/api-client'

import {
  createTemplate,
  deleteTemplate,
  fetchCategories,
  fetchOrders,
  fetchRevenue,
  fetchStats,
  fetchTemplates,
  setPublished,
  type AdminOrder,
  type AdminStats,
  type AdminTemplate,
  type Category,
  type MonthRevenue,
} from './api'
import styles from './AdminPage.module.css'

const LANGUAGES = [
  { code: 'ro', label: 'RO' },
  { code: 'ru', label: 'RU' },
  { code: 'en', label: 'EN' },
]

const MONTHS_RO = ['Ian', 'Feb', 'Mar', 'Apr', 'Mai', 'Iun', 'Iul', 'Aug', 'Sep', 'Oct', 'Noi', 'Dec']

function monthLabel(label: string): string {
  const month = Number(label.split('-')[1])
  return MONTHS_RO[month - 1] ?? label
}

const STATUS_LABEL: Record<string, string> = {
  paid: 'Plătită',
  pending: 'În așteptare',
  failed: 'Eșuată',
  cancelled: 'Anulată',
}

function RevenueChart({ data }: { data: MonthRevenue[] }) {
  const max = Math.max(1, ...data.map((d) => d.revenue_bani))
  return (
    <div className={styles.chart}>
      {data.map((d, i) => {
        const heightPct = (d.revenue_bani / max) * 100
        const current = i === data.length - 1
        return (
          <div key={d.label} className={styles.bar}>
            <div className={styles.barTrack}>
              <div
                className={current ? styles.barFillCurrent : styles.barFill}
                style={{ height: `${heightPct}%` }}
                title={`${d.revenue_mdl} MDL`}
              />
            </div>
            <span className={styles.barLabel}>{monthLabel(d.label)}</span>
          </div>
        )
      })}
    </div>
  )
}

function AddTemplateForm({
  categories,
  onCreated,
}: {
  categories: Category[]
  onCreated: (t: AdminTemplate) => void
}) {
  const [name, setName] = useState('')
  const [categoryId, setCategoryId] = useState('')
  const [description, setDescription] = useState('')
  const [priceMdl, setPriceMdl] = useState('')
  const [languages, setLanguages] = useState<string[]>(['ro'])
  const [isPublished, setIsPublished] = useState(false)
  const [file, setFile] = useState<File | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  function toggleLang(code: string) {
    setLanguages((cur) => (cur.includes(code) ? cur.filter((c) => c !== code) : [...cur, code]))
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    setError(null)

    if (!file) return setError('Încarcă un fișier .docx.')
    if (!categoryId) return setError('Alege o categorie.')
    if (languages.length === 0) return setError('Alege cel puțin o limbă.')
    // Admin enters MDL; the API stores bani. Integer multiply, no float drift.
    const priceBani = Math.round(Number(priceMdl) * 100)
    if (!Number.isFinite(priceBani) || priceBani <= 0) return setError('Preț invalid.')

    setBusy(true)
    try {
      const created = await createTemplate({
        name,
        categoryId,
        description,
        priceBani,
        languages,
        isPublished,
        file,
      })
      onCreated(created)
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : 'Nu am putut adăuga șablonul.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <form className={styles.form} onSubmit={handleSubmit}>
      <div className={styles.formGrid}>
        <label className={styles.formField}>
          <span className={styles.formLabel}>Nume</span>
          <input
            className={styles.formInput}
            value={name}
            onChange={(e) => setName(e.target.value)}
            minLength={2}
            required
          />
        </label>
        <label className={styles.formField}>
          <span className={styles.formLabel}>Categorie</span>
          <select
            className={styles.formInput}
            value={categoryId}
            onChange={(e) => setCategoryId(e.target.value)}
            required
          >
            <option value="">Alege…</option>
            {categories.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </select>
        </label>
        <label className={styles.formField}>
          <span className={styles.formLabel}>Preț (MDL)</span>
          <input
            className={styles.formInput}
            type="number"
            min="1"
            value={priceMdl}
            onChange={(e) => setPriceMdl(e.target.value)}
            required
          />
        </label>
        <label className={styles.formField}>
          <span className={styles.formLabel}>Document (.docx)</span>
          <input
            className={styles.formFile}
            type="file"
            accept=".docx"
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            required
          />
        </label>
      </div>

      <label className={styles.formField}>
        <span className={styles.formLabel}>Descriere</span>
        <textarea
          className={styles.formTextarea}
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          rows={2}
          required
        />
      </label>

      <div className={styles.formRow}>
        <div className={styles.langGroup}>
          <span className={styles.formLabel}>Limbi</span>
          <div className={styles.langChips}>
            {LANGUAGES.map((l) => (
              <button
                key={l.code}
                type="button"
                className={languages.includes(l.code) ? styles.langOn : styles.langOff}
                onClick={() => toggleLang(l.code)}
              >
                {l.label}
              </button>
            ))}
          </div>
        </div>
        <label className={styles.publishToggle}>
          <input
            type="checkbox"
            checked={isPublished}
            onChange={(e) => setIsPublished(e.target.checked)}
          />
          Publică imediat
        </label>
      </div>

      {error && (
        <p className={styles.formError} role="alert">
          {error}
        </p>
      )}

      <button type="submit" className={styles.formSubmit} disabled={busy}>
        {busy ? 'Se procesează documentul…' : 'Adaugă șablonul'}
      </button>
    </form>
  )
}

export function AdminPage() {
  const [stats, setStats] = useState<AdminStats | null>(null)
  const [revenue, setRevenue] = useState<MonthRevenue[]>([])
  const [orders, setOrders] = useState<AdminOrder[]>([])
  const [templates, setTemplates] = useState<AdminTemplate[]>([])
  const [categories, setCategories] = useState<Category[]>([])
  const [showForm, setShowForm] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    Promise.all([fetchStats(), fetchRevenue(), fetchOrders(), fetchTemplates(), fetchCategories()])
      .then(([s, r, o, t, c]) => {
        if (cancelled) return
        setStats(s)
        setRevenue(r)
        setOrders(o)
        setTemplates(t)
        setCategories(c)
      })
      .catch(() => !cancelled && setError('Nu am putut încărca panoul de administrare.'))
    return () => {
      cancelled = true
    }
  }, [])

  async function togglePublish(template: AdminTemplate) {
    try {
      const updated = await setPublished(template.id, !template.is_published)
      setTemplates((list) => list.map((t) => (t.id === updated.id ? updated : t)))
    } catch {
      setError('Nu am putut actualiza șablonul.')
    }
  }

  async function handleDelete(template: AdminTemplate) {
    if (!window.confirm(`Ștergi definitiv „${template.name}"?`)) return
    setError(null)
    try {
      await deleteTemplate(template.id)
      setTemplates((list) => list.filter((t) => t.id !== template.id))
    } catch (caught) {
      setError(
        caught instanceof ApiError && caught.status === 409
          ? 'Șablonul are vânzări și nu poate fi șters. Ascunde-l în schimb.'
          : 'Nu am putut șterge șablonul.',
      )
    }
  }

  function handleCreated(created: AdminTemplate) {
    setTemplates((list) => [created, ...list])
    setShowForm(false)
  }

  const kpis = stats
    ? [
        { label: 'Venituri totale', value: `${stats.revenue_mdl} MDL` },
        { label: 'Comenzi plătite', value: String(stats.paid_orders) },
        { label: 'Utilizatori', value: String(stats.users) },
        { label: 'Șabloane publicate', value: String(stats.published_templates) },
      ]
    : []

  return (
    <AppShell title="Panou de administrare" subtitle="Administrare internă">
      {error && (
        <p className={styles.error} role="alert">
          {error}
        </p>
      )}

      <section className={styles.kpis}>
        {kpis.map((k) => (
          <div key={k.label} className={styles.kpi}>
            <p className={styles.kpiLabel}>{k.label}</p>
            <p className={styles.kpiValue}>{k.value}</p>
          </div>
        ))}
      </section>

      <section className={styles.card}>
        <h2 className={styles.cardTitle}>Venituri lunare</h2>
        {revenue.length > 0 ? (
          <RevenueChart data={revenue} />
        ) : (
          <p className={styles.muted}>Niciun venit încă.</p>
        )}
      </section>

      <section className={styles.card}>
        <h2 className={styles.cardTitle}>Comenzi recente</h2>
        {orders.length === 0 ? (
          <p className={styles.muted}>Nicio comandă încă.</p>
        ) : (
          <div className={styles.tableWrap}>
            <table className={styles.table}>
              <thead>
                <tr>
                  <th>Comandă</th>
                  <th>Client</th>
                  <th>Document</th>
                  <th className={styles.right}>Sumă</th>
                  <th className={styles.right}>Status</th>
                </tr>
              </thead>
              <tbody>
                {orders.map((o) => (
                  <tr key={o.number}>
                    <td className={styles.mono}>{o.number}</td>
                    <td>
                      <div className={styles.client}>{o.client_name}</div>
                      <div className={styles.clientEmail}>{o.client_email}</div>
                    </td>
                    <td>
                      {o.first_item}
                      {o.item_count > 1 && <span className={styles.plus}> +{o.item_count - 1}</span>}
                    </td>
                    <td className={styles.right}>{o.total_mdl} MDL</td>
                    <td className={styles.right}>
                      <span className={`${styles.status} ${styles[`status_${o.status}`] ?? ''}`}>
                        {STATUS_LABEL[o.status] ?? o.status}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section className={styles.card}>
        <div className={styles.sectionHead}>
          <h2 className={styles.cardTitle}>Șabloane</h2>
          <button
            type="button"
            className={styles.addButton}
            onClick={() => setShowForm((open) => !open)}
          >
            {showForm ? 'Anulează' : '+ Adaugă șablon'}
          </button>
        </div>

        {showForm && (
          <AddTemplateForm categories={categories} onCreated={handleCreated} />
        )}

        <div className={styles.tableWrap}>
          <table className={styles.table}>
            <thead>
              <tr>
                <th>Nume</th>
                <th>Categorie</th>
                <th className={styles.right}>Preț</th>
                <th className={styles.right}>Stare</th>
                <th className={styles.right}>Acțiuni</th>
              </tr>
            </thead>
            <tbody>
              {templates.map((t) => (
                <tr key={t.id}>
                  <td>{t.name}</td>
                  <td className={styles.muted2}>{t.category_name}</td>
                  <td className={styles.right}>{t.price_mdl} MDL</td>
                  <td className={styles.right}>
                    <button
                      type="button"
                      className={t.is_published ? styles.togglePublished : styles.toggleHidden}
                      onClick={() => void togglePublish(t)}
                    >
                      {t.is_published ? 'Publicat' : 'Ascuns'}
                    </button>
                  </td>
                  <td className={styles.right}>
                    <button
                      type="button"
                      className={styles.deleteButton}
                      onClick={() => void handleDelete(t)}
                      aria-label={`Șterge ${t.name}`}
                    >
                      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.9">
                        <polyline points="3 6 5 6 21 6" />
                        <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
                      </svg>
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </AppShell>
  )
}

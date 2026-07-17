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

import { useEffect, useState } from 'react'

import { AppShell } from '@/app/layouts/AppShell'

import {
  fetchOrders,
  fetchRevenue,
  fetchStats,
  fetchTemplates,
  setPublished,
  type AdminOrder,
  type AdminStats,
  type AdminTemplate,
  type MonthRevenue,
} from './api'
import styles from './AdminPage.module.css'

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

export function AdminPage() {
  const [stats, setStats] = useState<AdminStats | null>(null)
  const [revenue, setRevenue] = useState<MonthRevenue[]>([])
  const [orders, setOrders] = useState<AdminOrder[]>([])
  const [templates, setTemplates] = useState<AdminTemplate[]>([])
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    Promise.all([fetchStats(), fetchRevenue(), fetchOrders(), fetchTemplates()])
      .then(([s, r, o, t]) => {
        if (cancelled) return
        setStats(s)
        setRevenue(r)
        setOrders(o)
        setTemplates(t)
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

  const kpis = stats
    ? [
        { label: 'Venituri totale', value: `${stats.revenue_mdl} MDL` },
        { label: 'Comenzi plătite', value: String(stats.paid_orders) },
        { label: 'Utilizatori', value: String(stats.users) },
        { label: 'Șabloane publicate', value: String(stats.published_templates) },
      ]
    : []

  return (
    <AppShell title="Panou de administrare" subtitle="Crowe Turcan Mikhailenko">
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
        <h2 className={styles.cardTitle}>Șabloane</h2>
        <div className={styles.tableWrap}>
          <table className={styles.table}>
            <thead>
              <tr>
                <th>Nume</th>
                <th>Categorie</th>
                <th className={styles.right}>Preț</th>
                <th className={styles.right}>Stare</th>
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
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </AppShell>
  )
}

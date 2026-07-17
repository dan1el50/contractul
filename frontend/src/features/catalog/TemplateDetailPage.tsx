/**
 * Detaliu Contract — one contract, with its preview and buy panel.
 *
 * Implements Detaliu Contract.dc.html, as revised on 2026-07-17: flat price,
 * no language selector. A document is one file containing every language it is
 * written in, so there is nothing to choose and nothing to multiply the price
 * by. The prototype keeps the old selector commented out if that ever returns.
 *
 * Retires Detaliu Contract.dc.html.
 */

import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'

import { AppShell } from '@/app/layouts/AppShell'
import { ApiError } from '@/lib/api-client'

import { fetchTemplate, previewUrl, type TemplateDetail } from './api'
import styles from './TemplateDetailPage.module.css'

const INCLUDED = [
  'Document conform legislației RM',
  'Toate limbile în același fișier',
  'Formate PDF și Word editabil',
  'Câmpuri completate automat din datele tale',
  'Actualizări gratuite la modificări legislative',
]

export function TemplateDetailPage() {
  const { slug = '' } = useParams()
  const [template, setTemplate] = useState<TemplateDetail | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    setError(null)
    setTemplate(null)

    fetchTemplate(slug)
      .then((detail) => !cancelled && setTemplate(detail))
      .catch((caught: unknown) => {
        if (cancelled) return
        setError(
          caught instanceof ApiError && caught.status === 404
            ? 'Contractul nu a fost găsit.'
            : 'Nu am putut încărca contractul.',
        )
      })

    return () => {
      cancelled = true
    }
  }, [slug])

  if (error) {
    return (
      <AppShell title="Contract">
        <p className={styles.error} role="alert">
          {error}
        </p>
        <Link to="/" className={styles.back}>
          ← Înapoi la panoul principal
        </Link>
      </AppShell>
    )
  }

  if (!template) {
    return (
      <AppShell title="Contract">
        <p className={styles.loading}>Se încarcă…</p>
      </AppShell>
    )
  }

  const lockedPages = Array.from(
    { length: Math.max(0, template.page_count - template.free_pages) },
    (_, i) => template.free_pages + i + 1,
  )

  return (
    <AppShell title={template.name} subtitle={template.category.name}>
      <div className={styles.layout}>
        <div className={styles.left}>
          <section className={styles.intro}>
            <span className={styles.catBadge}>{template.category.name}</span>
            <h2 className={styles.name}>{template.name}</h2>
            <p className={styles.description}>{template.description}</p>
          </section>

          <section className={styles.card}>
            <h3 className={styles.cardTitle}>Ce include</h3>
            <ul className={styles.included}>
              {INCLUDED.map((item) => (
                <li key={item} className={styles.includedItem}>
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="var(--color-teal)" strokeWidth="2.4" aria-hidden="true">
                    <path d="M20 6 9 17l-5-5" />
                  </svg>
                  {item}
                </li>
              ))}
            </ul>
          </section>

          <section className={styles.card}>
            <div className={styles.previewHead}>
              <h3 className={styles.cardTitle}>Previzualizare document</h3>
              <span className={styles.pageCount}>
                Pagina {template.free_pages} din {template.page_count}
              </span>
            </div>

            <div className={styles.pageFrame}>
              <img
                src={previewUrl(template.slug, 1)}
                alt={`Pagina 1 din ${template.name}`}
                className={styles.pageImage}
                loading="lazy"
              />
            </div>

            {lockedPages.length > 0 && (
              <div className={styles.lockedWrap}>
                {/* The blur here is decoration. The image behind it is rendered
                    at a resolution too low to read, so opening it directly or
                    deleting this style reveals nothing. The API decides that
                    from the page number — there is no way to ask for more. */}
                <div className={styles.lockedBlur}>
                  <img
                    src={previewUrl(template.slug, lockedPages[0] ?? 2)}
                    alt=""
                    aria-hidden="true"
                    className={styles.pageImage}
                    loading="lazy"
                  />
                </div>

                <div className={styles.lockOverlay}>
                  <span className={styles.lockIcon} aria-hidden="true">
                    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="var(--color-amber)" strokeWidth="2">
                      <rect x="3" y="11" width="18" height="11" rx="2" />
                      <path d="M7 11V7a5 5 0 0 1 10 0v4" />
                    </svg>
                  </span>
                  <p className={styles.lockTitle}>Restul documentului este blocat</p>
                  <p className={styles.lockText}>
                    Cumpără contractul pentru a debloca toate cele {template.page_count} pagini, în
                    PDF și Word editabil.
                  </p>
                </div>
              </div>
            )}
          </section>
        </div>

        <aside className={styles.buyPanel}>
          <p className={styles.priceLabel}>Preț</p>
          <p className={styles.price}>
            {template.price_mdl} <span className={styles.priceUnit}>MDL</span>
          </p>
          <p className={styles.priceNote}>Preț unic, indiferent de limbă</p>

          <div className={styles.langBox}>
            <svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="var(--color-teal)" strokeWidth="1.9" aria-hidden="true">
              <circle cx="12" cy="12" r="10" />
              <path d="M2 12h20" />
              <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z" />
            </svg>
            <div>
              <p className={styles.langText}>
                Limbi incluse: <strong>{template.languages.join(', ').toUpperCase()}</strong>
              </p>
              <p className={styles.langHint}>Toate limbile sunt în același document</p>
            </div>
          </div>

          <div className={styles.formatBox}>
            <svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="var(--color-blue)" strokeWidth="1.9" aria-hidden="true">
              <path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z" />
              <path d="M14 3v5h5" />
            </svg>
            <p className={styles.formatText}>
              Primești în <strong>PDF + Word editabil</strong>
            </p>
          </div>

          {/* The cart arrives in phase 6. Disabled rather than absent, so the
              panel reads the way it will — and so nobody thinks it is broken. */}
          <button type="button" className={styles.addToCart} disabled title="Disponibil în curând">
            <svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.1" aria-hidden="true">
              <circle cx="9" cy="20" r="1.4" />
              <circle cx="18" cy="20" r="1.4" />
              <path d="M2 3h3l2.4 12.4a2 2 0 0 0 2 1.6h8a2 2 0 0 0 2-1.6L22 7H6" />
            </svg>
            Adaugă în coș
          </button>
          <p className={styles.soon}>Coșul și plata vin în faza 6.</p>

          <div className={styles.divider} />
          <p className={styles.verified}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="var(--color-teal)" strokeWidth="2" aria-hidden="true">
              <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
            </svg>
            Verificat juridic de Crowe
          </p>
        </aside>
      </div>
    </AppShell>
  )
}

/**
 * The contract catalog — the shop.
 *
 * Public: browsable signed in or out. BrowseLayout gives it the sidebar when
 * signed in and the marketing chrome when not.
 *
 * Implements Catalog Sabloane.dc.html. Retires Catalog Sabloane.dc.html.
 */

import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'

import { BrowseLayout } from '@/app/layouts/BrowseLayout'
import { ApiError } from '@/lib/api-client'

import { fetchCategories, fetchTemplates, type Category, type TemplateSummary } from './api'
import styles from './CatalogPage.module.css'

const ALL = 'toate'

export function CatalogPage() {
  const [params, setParams] = useSearchParams()
  const active = params.get('categorie') ?? ALL

  const [categories, setCategories] = useState<Category[]>([])
  const [templates, setTemplates] = useState<TemplateSummary[]>([])
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    fetchCategories()
      .then((list) => !cancelled && setCategories(list))
      .catch(() => {
        /* The chips are a refinement; losing them must not blank the page. */
      })
    return () => {
      cancelled = true
    }
  }, [])

  // The filter lives in the URL, not in state — so a filtered catalog can be
  // linked, bookmarked, and survives a reload.
  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)

    fetchTemplates(active === ALL ? undefined : active)
      .then((list) => !cancelled && setTemplates(list))
      .catch((caught: unknown) => {
        if (cancelled) return
        setError(
          caught instanceof ApiError ? caught.message : 'Nu am putut încărca contractele.',
        )
      })
      .finally(() => !cancelled && setLoading(false))

    return () => {
      cancelled = true
    }
  }, [active])

  function selectCategory(slug: string) {
    setParams(slug === ALL ? {} : { categorie: slug }, { replace: true })
  }

  return (
    <BrowseLayout
      title="Catalog de contracte"
      subtitle="Contracte verificate juridic de Crowe Turcan Mikhailenko"
    >
      <div className={styles.chips}>
        <button
          type="button"
          className={active === ALL ? styles.chipOn : styles.chip}
          onClick={() => selectCategory(ALL)}
        >
          Toate
        </button>
        {categories.map((category) => (
          <button
            key={category.slug}
            type="button"
            className={active === category.slug ? styles.chipOn : styles.chip}
            onClick={() => selectCategory(category.slug)}
          >
            {category.name}
          </button>
        ))}
      </div>

      {error && (
        <p className={styles.error} role="alert">
          {error}
        </p>
      )}

      {!error && (
        <p className={styles.count}>
          {loading ? 'Se încarcă…' : `Afișare ${templates.length} șabloane`}
        </p>
      )}

      {!loading && !error && templates.length === 0 && (
        <p className={styles.empty}>Nu există contracte în această categorie.</p>
      )}

      <div className={styles.grid}>
        {templates.map((template) => (
          <Link key={template.id} to={`/contract/${template.slug}`} className={styles.card}>
            <div className={styles.cardTop}>
              <span className={styles.cardIcon} aria-hidden="true">
                <svg width="23" height="23" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7">
                  <path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z" />
                  <path d="M14 3v5h5" />
                  <line x1="9" y1="13" x2="15" y2="13" />
                  <line x1="9" y1="17" x2="13" y2="17" />
                </svg>
              </span>
              <span className={styles.cardCat}>{template.category.name}</span>
            </div>

            <div className={styles.cardBody}>
              <h2 className={styles.cardTitle}>{template.name}</h2>
              <p className={styles.cardDesc}>{template.description}</p>
            </div>

            <div className={styles.cardFoot}>
              <div>
                <p className={styles.priceLabel}>Preț</p>
                <p className={styles.price}>{template.price_mdl} MDL</p>
              </div>
              <span className={styles.langs}>{template.languages.join(', ').toUpperCase()}</span>
            </div>
          </Link>
        ))}
      </div>
    </BrowseLayout>
  )
}

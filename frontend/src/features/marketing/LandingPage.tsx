/**
 * The public landing page.
 *
 * Implements Landing.dc.html. Retires Landing.dc.html.
 *
 * Two deliberate departures from the prototype, both to keep the page honest:
 *
 * - **No invented metrics.** The prototype hero boasts "36+ tipuri" and
 *   "1 480+ documente vândute". We have neither number, so the counts here are
 *   read live from the catalog — whatever is really published.
 * - **No "20% bonus" and no "factură fiscală automată".** There is no top-up
 *   bonus (nobody specified one — see WalletPage) and we issue no fiscal
 *   invoice (which is why order numbers are allowed to have gaps). Advertising
 *   either would be advertising something that does not exist.
 */

import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'

import { PublicLayout } from '@/app/layouts/PublicLayout'
import {
  fetchCategories,
  fetchTemplates,
  type Category,
  type TemplateSummary,
} from '@/features/catalog/api'

import indigoTexture from '@/assets/smartpath-indigo.png'
import amberTexture from '@/assets/smartpath-amber.png'
import styles from './LandingPage.module.css'

/** Per-category colour and glyph, keyed by slug, from the prototype. */
const CATEGORY_ART: Record<string, { bg: string; fg: string; paths: string[] }> = {
  servicii: { bg: '#FEF6E4', fg: '#B26A00', paths: ['M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z', 'M14 3v5h5'] },
  imobiliare: { bg: '#E4F5F1', fg: '#0C7876', paths: ['M3 21h18', 'M5 21V7l8-4v18', 'M19 21V11l-6-4'] },
  vanzare: { bg: '#EEF3FB', fg: '#003F9F', paths: ['M2 3h3l2.4 12.4a2 2 0 0 0 2 1.6h8a2 2 0 0 0 2-1.6L22 7H6'] },
  munca: { bg: '#FEF6E4', fg: '#B26A00', paths: ['M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2', 'M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8z'] },
  confidentialitate: { bg: '#EEF3FB', fg: '#003F9F', paths: ['M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z'] },
  transport: { bg: '#E4F5F1', fg: '#0C7876', paths: ['M1 3h15v13H1z', 'M16 8h4l3 3v5h-7', 'M5.5 21a2.5 2.5 0 1 0 0-5 2.5 2.5 0 0 0 0 5z', 'M18.5 21a2.5 2.5 0 1 0 0-5 2.5 2.5 0 0 0 0 5z'] },
}

const FALLBACK_ART = { bg: '#EEF3FB', fg: '#003F9F', paths: ['M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z', 'M14 3v5h5'] }

const STEPS = [
  { n: '1', title: 'Alege contractul', desc: 'Selectezi tipul de contract din magazin, filtrat pe categorii.' },
  { n: '2', title: 'Completează datele', desc: 'Un formular ghidat te întreabă doar ce e necesar.' },
  { n: '3', title: 'Plătește', desc: 'Din portofel sau cu cardul, direct în platformă. Securizat.' },
  { n: '4', title: 'Descarcă', desc: 'Primești contractul în PDF și Word editabil, gata de semnat.' },
]

const PER_DOC_PERKS = [
  'Fără abonament, fără obligații',
  'PDF + Word editabil',
  'Actualizat la legislația în vigoare',
]

const WALLET_PERKS = [
  'Alimentezi o singură dată și cumperi orice contract instant',
  'Un singur sold pentru toate documentele',
  'Istoric complet al tranzacțiilor tale',
]

/** The lowest price in a set of templates, already formatted by the API. */
function cheapestMdl(templates: TemplateSummary[]): string | null {
  if (templates.length === 0) return null
  return templates.reduce((min, t) => (t.price_bani < min.price_bani ? t : min)).price_mdl
}

function Check({ stroke }: { stroke: string }) {
  return (
    <svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke={stroke} strokeWidth="2.4" style={{ flexShrink: 0 }} aria-hidden="true">
      <path d="M20 6 9 17l-5-5" />
    </svg>
  )
}

export function LandingPage() {
  const [categories, setCategories] = useState<Category[]>([])
  const [templates, setTemplates] = useState<TemplateSummary[]>([])

  useEffect(() => {
    let cancelled = false
    Promise.all([fetchCategories(), fetchTemplates()])
      .then(([cats, temps]) => {
        if (cancelled) return
        setCategories(cats)
        setTemplates(temps)
      })
      .catch(() => {
        /* The store section degrades to empty; the page still stands. */
      })
    return () => {
      cancelled = true
    }
  }, [])

  const fromPrice = cheapestMdl(templates)

  return (
    <PublicLayout>
      {/* ─── Hero ─────────────────────────────────────────────────────── */}
      <section className={styles.hero}>
        <div className={styles.heroTexture} style={{ backgroundImage: `url(${indigoTexture})` }} />
        <div className={styles.heroFade} />
        <div className={styles.heroInner}>
          <div>
            <div className={styles.badge}>
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="var(--color-amber)" strokeWidth="2.2" aria-hidden="true">
                <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
              </svg>
              <span>Verificate juridic de Crowe Turcan Mikhailenko</span>
            </div>
            <h1 className={styles.heroTitle}>
              Contracte gata de semnat,
              <br />
              în câteva minute
            </h1>
            <p className={styles.heroText}>
              Alegi un contract, completezi datele, plătești și îl descarci în PDF și Word. Fără
              avocat, fără așteptare — documente conforme legislației Republicii Moldova.
            </p>
            <div className={styles.heroActions}>
              <Link to="/catalog" className={styles.primaryBtn}>
                Alege un contract
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="var(--color-navy)" strokeWidth="2.4" aria-hidden="true">
                  <polyline points="9 18 15 12 9 6" />
                </svg>
              </Link>
              <a href="#cum" className={styles.ghostBtn}>
                Cum funcționează
              </a>
            </div>
            {templates.length > 0 && (
              <div className={styles.stats}>
                <div>
                  <p className={styles.statNum}>{templates.length}</p>
                  <p className={styles.statLabel}>tipuri de contracte</p>
                </div>
                <div className={styles.statRule} />
                <div>
                  <p className={styles.statNum}>{categories.length}</p>
                  <p className={styles.statLabel}>categorii juridice</p>
                </div>
              </div>
            )}
          </div>

          <div className={styles.heroCardWrap}>
            <div className={styles.heroCard}>
              <p className={styles.docTitle}>CONTRACT DE PRESTĂRI SERVICII</p>
              <div className={styles.docRule} />
              <div className={styles.docLines}>
                <span style={{ width: '100%' }} />
                <span style={{ width: '92%' }} />
                <span className={styles.docLineHi} style={{ width: '60%' }} />
                <span style={{ width: '100%' }} />
                <span style={{ width: '78%' }} />
              </div>
              <div className={styles.docRule} />
              <div className={styles.docSign}>
                <div className={styles.docSignCol} />
                <div className={styles.docSignCol} />
              </div>
              <div className={styles.docSeal} aria-hidden="true">
                <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="2.6">
                  <path d="M20 6 9 17l-5-5" />
                </svg>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ─── Store ────────────────────────────────────────────────────── */}
      <section id="catalog" className={styles.store}>
        <div className={styles.sectionHead}>
          <p className={styles.eyebrow}>Magazin de contracte</p>
          <h2 className={styles.sectionTitle}>Alege categoria de care ai nevoie</h2>
          <p className={styles.sectionSub}>
            Fiecare contract este redactat și actualizat de juriștii Crowe.
          </p>
        </div>

        <div className={styles.catGrid}>
          {categories.map((category) => {
            const art = CATEGORY_ART[category.slug] ?? FALLBACK_ART
            const inCategory = templates.filter((t) => t.category.slug === category.slug)
            const from = cheapestMdl(inCategory)
            return (
              <Link
                key={category.slug}
                to={`/catalog?categorie=${encodeURIComponent(category.slug)}`}
                className={styles.catCard}
              >
                <span className={styles.catIcon} style={{ background: art.bg, color: art.fg }}>
                  <svg width="25" height="25" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7">
                    {art.paths.map((d) => (
                      <path key={d} d={d} />
                    ))}
                  </svg>
                </span>
                <div className={styles.catBody}>
                  <h3 className={styles.catName}>{category.name}</h3>
                  {category.description && <p className={styles.catDesc}>{category.description}</p>}
                </div>
                <div className={styles.catFoot}>
                  <span className={styles.catCount}>{inCategory.length} șabloane</span>
                  {from && <span className={styles.catPrice}>de la {from} MDL</span>}
                </div>
              </Link>
            )
          })}
        </div>
      </section>

      {/* ─── How it works ─────────────────────────────────────────────── */}
      <section id="cum" className={styles.how}>
        <div className={styles.howInner}>
          <div className={styles.sectionHead}>
            <p className={styles.eyebrow}>Simplu în 4 pași</p>
            <h2 className={styles.sectionTitle}>Cum funcționează</h2>
          </div>
          <div className={styles.steps}>
            {STEPS.map((step) => (
              <div key={step.n} className={styles.step}>
                <span className={styles.stepNum}>{step.n}</span>
                <h3 className={styles.stepTitle}>{step.title}</h3>
                <p className={styles.stepDesc}>{step.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ─── Pricing ──────────────────────────────────────────────────── */}
      <section id="preturi" className={styles.pricing}>
        <div className={styles.priceGrid}>
          <div className={styles.priceCard}>
            <p className={styles.priceKicker}>Plată per document</p>
            <p className={styles.priceValue}>{fromPrice ? `de la ${fromPrice} MDL` : 'Preț unic'}</p>
            <p className={styles.priceLead}>
              Plătești doar contractul de care ai nevoie, când ai nevoie.
            </p>
            <div className={styles.priceRule} />
            <div className={styles.perks}>
              {PER_DOC_PERKS.map((perk) => (
                <div key={perk} className={styles.perk}>
                  <Check stroke="var(--color-teal)" />
                  <span>{perk}</span>
                </div>
              ))}
            </div>
            <Link to="/catalog" className={styles.priceBtnOutline}>
              Vezi contractele
            </Link>
          </div>

          <div className={styles.priceCardDark}>
            <div className={styles.priceTexture} style={{ backgroundImage: `url(${amberTexture})` }} />
            <div className={styles.priceDarkInner}>
              <span className={styles.recommend}>Recomandat</span>
              <p className={styles.priceKickerLight}>Portofel Contracte</p>
              <p className={styles.priceValueLight}>Alimentează contul</p>
              <p className={styles.priceLeadLight}>
                Încarci o sumă o singură dată și cumperi orice contract instant, fără să introduci
                cardul de fiecare dată.
              </p>
              <div className={styles.priceRuleLight} />
              <div className={styles.perks}>
                {WALLET_PERKS.map((perk) => (
                  <div key={perk} className={styles.perkLight}>
                    <Check stroke="var(--color-amber)" />
                    <span>{perk}</span>
                  </div>
                ))}
              </div>
              <Link to="/portofel" className={styles.priceBtnAmber}>
                Alimentează contul
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="var(--color-navy)" strokeWidth="2.4" aria-hidden="true">
                  <polyline points="9 18 15 12 9 6" />
                </svg>
              </Link>
            </div>
          </div>
        </div>
      </section>

      {/* ─── CTA strip ────────────────────────────────────────────────── */}
      <section className={styles.cta}>
        <div className={styles.ctaInner}>
          <div>
            <h2 className={styles.ctaTitle}>Ai nevoie de un contract chiar acum?</h2>
            <p className={styles.ctaText}>Alege, completează, descarcă.</p>
          </div>
          <Link to="/catalog" className={styles.ctaBtn}>
            Începe acum
          </Link>
        </div>
      </section>
    </PublicLayout>
  )
}

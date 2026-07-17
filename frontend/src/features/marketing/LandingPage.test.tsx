/**
 * The public landing page.
 *
 * fetch is stubbed: this covers what the page renders from catalog data, not
 * the catalog API itself, which has its own tests against a real database.
 */

import { render, screen, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { AuthProvider } from '@/features/auth/AuthContext'

import { LandingPage } from './LandingPage'

const CATEGORIES = [
  { id: 'c1', slug: 'servicii', name: 'Servicii & Colaborare', description: 'Prestări servicii.' },
  { id: 'c2', slug: 'transport', name: 'Transport & Livrare', description: 'Transport de mărfuri.' },
]

const TEMPLATES = [
  {
    id: 't1',
    slug: 'prestari-servicii',
    name: 'Contract de prestări servicii',
    description: 'x',
    price_bani: 90000,
    price_mdl: '900',
    languages: ['ro', 'ru'],
    category: CATEGORIES[0],
  },
  {
    id: 't2',
    slug: 'colaborare',
    name: 'Contract de colaborare',
    description: 'x',
    price_bani: 100000,
    price_mdl: '1 000',
    languages: ['ro', 'ru'],
    category: CATEGORIES[0],
  },
  {
    id: 't3',
    slug: 'transport-marfuri',
    name: 'Contract de transport',
    description: 'x',
    price_bani: 120000,
    price_mdl: '1 200',
    languages: ['ro', 'ru'],
    category: CATEGORIES[1],
  },
]

function json(body: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: () => Promise.resolve(body),
  } as Response
}

function stubCatalog() {
  vi.stubGlobal(
    'fetch',
    vi.fn((url: string) => {
      if (url.includes('/auth/me')) return json({ detail: 'Autentificare necesară.' }, 401)
      if (url.includes('/categories')) return json(CATEGORIES)
      if (url.includes('/templates')) return json(TEMPLATES)
      return json({}, 404)
    }),
  )
}

function renderPage() {
  return render(
    <MemoryRouter>
      <AuthProvider>
        <LandingPage />
      </AuthProvider>
    </MemoryRouter>,
  )
}

beforeEach(stubCatalog)
afterEach(() => vi.unstubAllGlobals())

describe('LandingPage', () => {
  it('shows the hero headline', async () => {
    renderPage()
    expect(await screen.findByText(/Contracte gata de semnat/)).toBeInTheDocument()
  })

  it('reports real counts from the catalog, not invented ones', async () => {
    renderPage()

    // Three templates across two categories were served.
    const tipuri = (await screen.findByText('tipuri de contracte')).closest('div') as HTMLElement
    expect(within(tipuri).getByText('3')).toBeInTheDocument()
    const categorii = screen.getByText('categorii juridice').closest('div') as HTMLElement
    expect(within(categorii).getByText('2')).toBeInTheDocument()

    // The prototype's fabricated "1 480+ documente vândute" must not appear.
    expect(screen.queryByText(/1 480/)).not.toBeInTheDocument()
    expect(screen.queryByText(/documente vândute/)).not.toBeInTheDocument()
  })

  it('renders a card per category with its template count and cheapest price', async () => {
    renderPage()

    const servicii = await screen.findByText('Servicii & Colaborare')
    const card = servicii.closest('a') as HTMLElement
    // Two templates in this category; cheapest is 900.
    expect(within(card).getByText('2 șabloane')).toBeInTheDocument()
    expect(within(card).getByText('de la 900 MDL')).toBeInTheDocument()
    expect(card).toHaveAttribute('href', '/catalog?categorie=servicii')
  })

  it('advertises neither a top-up bonus nor a fiscal invoice, because we offer neither', async () => {
    renderPage()
    await screen.findByText(/Contracte gata de semnat/)

    // Both are in the prototype and both are false for us — see the page's docstring.
    expect(screen.queryByText(/20%/)).not.toBeInTheDocument()
    expect(screen.queryByText(/bonus/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/factură fiscală/i)).not.toBeInTheDocument()
  })

  it('derives the "from" price as the cheapest template overall', async () => {
    renderPage()
    // 900 is cheaper than 1 200.
    expect(await screen.findByText('de la 900 MDL', { selector: 'p' })).toBeInTheDocument()
  })
})

/**
 * The auth screen.
 *
 * fetch is stubbed: this covers the form's behaviour, not the API's — the API
 * has its own tests, against a real database.
 */

import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { AuthProvider } from './AuthContext'
import { AuthPage } from './AuthPage'

const USER = {
  id: 'b7e9c1e0-0000-4000-8000-000000000000',
  email: 'ion@nordconstruct.md',
  full_name: 'Ion Popescu',
  phone: null,
  is_admin: false,
}

/** Not signed in, so the AuthProvider's boot check answers 401. */
function stubFetch(handler: (url: string, init?: RequestInit) => Response | Promise<Response>) {
  vi.stubGlobal('fetch', vi.fn((url: string, init?: RequestInit) => handler(url, init)))
}

function json(body: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: () => Promise.resolve(body),
  } as Response
}

function renderPage() {
  return render(
    <MemoryRouter>
      <AuthProvider>
        <AuthPage />
      </AuthProvider>
    </MemoryRouter>,
  )
}

beforeEach(() => {
  stubFetch((url) =>
    url.includes('/auth/me') ? json({ detail: 'Autentificare necesară.' }, 401) : json(USER, 201),
  )
})

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('AuthPage', () => {
  it('opens on the registration form', async () => {
    renderPage()

    expect(await screen.findByText('Creează-ți contul')).toBeInTheDocument()
    expect(screen.getByLabelText('Nume complet')).toBeInTheDocument()
  })

  it('switches to login and drops the name field', async () => {
    const user = userEvent.setup()
    renderPage()

    await user.click(screen.getByRole('tab', { name: 'Autentificare' }))

    expect(await screen.findByText('Bine ai revenit')).toBeInTheDocument()
    expect(screen.queryByLabelText('Nume complet')).not.toBeInTheDocument()
  })

  it('sends credentials as cookies, not as a bearer token', async () => {
    // The session is an httpOnly cookie the browser attaches itself. Without
    // credentials:'include' it is never sent, every request looks signed out,
    // and nothing errors — it just silently does not work.
    const user = userEvent.setup()
    // init must be declared even though it is unused here, or the recorded
    // call tuple has no second element for the assertion below to read.
    const fetchMock = vi.fn((url: string, _init?: RequestInit) =>
      url.includes('/auth/me') ? json({}, 401) : json(USER, 201),
    )
    vi.stubGlobal('fetch', fetchMock)

    renderPage()
    await user.type(screen.getByLabelText('Nume complet'), 'Ion Popescu')
    await user.type(screen.getByLabelText('Email'), 'ion@nordconstruct.md')
    await user.type(screen.getByLabelText('Parolă'), 'parola-mea-sigura-2026')
    await user.click(screen.getByRole('button', { name: 'Creează cont' }))

    await waitFor(() => {
      const register = fetchMock.mock.calls.find(([url]) => url.includes('/auth/register'))
      expect(register).toBeDefined()
      expect(register?.[1]?.credentials).toBe('include')
    })
  })

  it("shows the API's error message rather than inventing one", async () => {
    // The API's wording is deliberately careful not to reveal whether an
    // account exists. Rewriting it in the UI would undo that.
    const user = userEvent.setup()
    stubFetch((url) =>
      url.includes('/auth/me')
        ? json({}, 401)
        : json({ detail: 'Un cont cu acest email există deja.' }, 409),
    )

    renderPage()
    await user.type(screen.getByLabelText('Nume complet'), 'Ion Popescu')
    await user.type(screen.getByLabelText('Email'), 'ion@nordconstruct.md')
    await user.type(screen.getByLabelText('Parolă'), 'parola-mea-sigura-2026')
    await user.click(screen.getByRole('button', { name: 'Creează cont' }))

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Un cont cu acest email există deja.',
    )
  })

  it('clears the error when switching tabs', async () => {
    const user = userEvent.setup()
    stubFetch((url) =>
      url.includes('/auth/me') ? json({}, 401) : json({ detail: 'Eroare de test.' }, 409),
    )

    renderPage()
    await user.type(screen.getByLabelText('Nume complet'), 'Ion Popescu')
    await user.type(screen.getByLabelText('Email'), 'ion@nordconstruct.md')
    await user.type(screen.getByLabelText('Parolă'), 'parola-mea-sigura-2026')
    await user.click(screen.getByRole('button', { name: 'Creează cont' }))
    expect(await screen.findByRole('alert')).toBeInTheDocument()

    await user.click(screen.getByRole('tab', { name: 'Autentificare' }))

    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })

  it('never puts the password in the DOM as readable text', async () => {
    const user = userEvent.setup()
    renderPage()

    const password = await screen.findByLabelText('Parolă')
    await user.type(password, 'parola-mea-sigura-2026')

    expect(password).toHaveAttribute('type', 'password')
    expect(document.body.textContent).not.toContain('parola-mea-sigura-2026')
  })
})

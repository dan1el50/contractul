/**
 * Proves the last link of the walking skeleton: that React actually renders
 * what the API returned.
 *
 * The other links are verified by running the stack — the API reaches
 * PostgreSQL, CORS allows the browser origin. This covers the part a curl
 * cannot see.
 *
 * fetch is stubbed rather than hitting a real backend: a unit test that needs
 * a database running is not a unit test.
 */

import { render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { SystemStatus } from './SystemStatus'

function stubFetch(body: unknown, status = 200) {
  vi.stubGlobal(
    'fetch',
    vi.fn().mockResolvedValue({
      ok: status >= 200 && status < 300,
      status,
      json: () => Promise.resolve(body),
    }),
  )
}

const healthyBody = {
  status: 'ok',
  service: 'contractul-backend',
  version: '0.1.0',
  environment: 'development',
  database: { connected: true, migration_revision: '0001_baseline', error: null },
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('SystemStatus', () => {
  it('renders the migration revision returned by the API', async () => {
    stubFetch(healthyBody)

    render(<SystemStatus />)

    // The revision is the proof: it exists nowhere in the frontend, so seeing
    // it on screen means it travelled database -> API -> browser.
    expect(await screen.findByText('0001_baseline')).toBeInTheDocument()
    expect(screen.getByText('conectată')).toBeInTheDocument()
  })

  it('surfaces the backend explanation when the database is unreachable', async () => {
    stubFetch(
      {
        ...healthyBody,
        status: 'degraded',
        database: { connected: false, migration_revision: null, error: 'Cannot read alembic_version.' },
      },
      503,
    )

    render(<SystemStatus />)

    expect(await screen.findByText('indisponibilă')).toBeInTheDocument()
    expect(screen.getByText('Cannot read alembic_version.')).toBeInTheDocument()
  })

  it('reports an unreachable API rather than rendering nothing', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')))

    render(<SystemStatus />)

    expect(await screen.findByText(/Cannot reach the API/)).toBeInTheDocument()
  })
})

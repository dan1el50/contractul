/**
 * The walking skeleton's one screen.
 *
 * Its job is to prove the chain: this component runs in the browser, calls the
 * API, which queries PostgreSQL, and what you see is what came back. When the
 * migration revision below reads "0001_baseline", every layer of the stack is
 * connected — that string exists nowhere but in the database.
 *
 * Deleted in phase 4, when real screens arrive.
 */

import { useEffect, useState, type CSSProperties } from 'react'

import { ApiError } from '@/lib/api-client'

import { fetchHealth, type Health } from './api'

type State =
  | { phase: 'loading' }
  | { phase: 'loaded'; health: Health }
  | { phase: 'unreachable'; message: string }

export function SystemStatus() {
  const [state, setState] = useState<State>({ phase: 'loading' })

  useEffect(() => {
    let cancelled = false

    fetchHealth()
      .then((health) => {
        if (!cancelled) setState({ phase: 'loaded', health })
      })
      .catch((error: unknown) => {
        if (cancelled) return
        setState({
          phase: 'unreachable',
          message: error instanceof ApiError ? error.message : 'Unexpected error',
        })
      })

    // The response can arrive after the component is gone — in development
    // StrictMode guarantees it — and setting state then is a warning at best.
    return () => {
      cancelled = true
    }
  }, [])

  return (
    <main style={styles.page}>
      <section style={styles.card}>
        <header style={styles.header}>
          <h1 style={styles.title}>Contracte.md</h1>
          <p style={styles.subtitle}>Crowe Turcan Mikhailenko</p>
        </header>

        <div style={styles.body}>
          <p style={styles.phase}>Faza 0 — schelet funcțional</p>

          {state.phase === 'loading' && <p style={styles.muted}>Se verifică sistemul…</p>}

          {state.phase === 'unreachable' && (
            <Row label="API" value={state.message} tone="bad" />
          )}

          {state.phase === 'loaded' && (
            <>
              <Row
                label="API"
                value={`${state.health.service} v${state.health.version}`}
                tone="good"
              />
              <Row
                label="Bază de date"
                value={state.health.database.connected ? 'conectată' : 'indisponibilă'}
                tone={state.health.database.connected ? 'good' : 'bad'}
              />
              <Row
                label="Migrare aplicată"
                value={state.health.database.migration_revision ?? '—'}
                tone={state.health.database.migration_revision ? 'good' : 'bad'}
                mono
              />
              <Row label="Mediu" value={state.health.environment} tone="neutral" />
              {state.health.database.error && (
                <p style={styles.error}>{state.health.database.error}</p>
              )}
            </>
          )}
        </div>
      </section>
    </main>
  )
}

function Row({
  label,
  value,
  tone,
  mono = false,
}: {
  label: string
  value: string
  tone: 'good' | 'bad' | 'neutral'
  mono?: boolean
}) {
  const dotColor = {
    good: 'var(--color-teal)',
    bad: 'var(--color-danger)',
    neutral: 'var(--color-text-subtle)',
  }[tone]

  return (
    <div style={styles.row}>
      <span style={styles.rowLabel}>{label}</span>
      <span style={styles.rowValue}>
        <span style={{ ...styles.dot, background: dotColor }} aria-hidden="true" />
        <span style={mono ? styles.mono : undefined}>{value}</span>
      </span>
    </div>
  )
}

/**
 * Inline styles here only because this screen is temporary and has no design
 * system to belong to yet. Real screens use tokens via CSS — see
 * docs/project-structure.md#the-dependency-rule.
 */
const styles = {
  page: {
    minHeight: '100vh',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    padding: 'var(--space-6)',
  },
  card: {
    width: '100%',
    maxWidth: 460,
    background: 'var(--color-surface)',
    border: '1px solid var(--color-border)',
    borderRadius: 'var(--radius-card)',
    overflow: 'hidden',
    boxShadow: '0 12px 30px rgba(1, 30, 65, 0.08)',
  },
  header: {
    background: 'var(--color-navy)',
    padding: 'var(--space-6)',
    borderBottom: '3px solid var(--color-amber)',
  },
  title: { color: '#fff', fontSize: 22, fontWeight: 700, letterSpacing: '-0.01em' },
  subtitle: { color: 'rgba(255,255,255,0.6)', fontSize: 13, marginTop: 4 },
  body: { padding: 'var(--space-6)' },
  phase: {
    fontSize: 11,
    fontWeight: 700,
    letterSpacing: '0.12em',
    textTransform: 'uppercase',
    color: 'var(--color-text-subtle)',
    marginBottom: 'var(--space-4)',
  },
  row: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    gap: 'var(--space-4)',
    padding: '11px 0',
    borderTop: '1px solid #f1f3f6',
    fontSize: 14,
  },
  rowLabel: { color: 'var(--color-text-muted)' },
  rowValue: { display: 'flex', alignItems: 'center', gap: 8, fontWeight: 600, textAlign: 'right' },
  dot: { width: 8, height: 8, borderRadius: '50%', flexShrink: 0 },
  mono: { fontFamily: 'var(--font-mono)', fontSize: 13 },
  muted: { color: 'var(--color-text-muted)', fontSize: 14 },
  error: {
    marginTop: 'var(--space-4)',
    padding: 'var(--space-3)',
    background: '#fdf2f2',
    borderRadius: 'var(--radius-control)',
    color: 'var(--color-danger)',
    fontSize: 12.5,
    lineHeight: 1.5,
  },
} satisfies Record<string, CSSProperties>

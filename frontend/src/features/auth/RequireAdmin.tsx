/**
 * Renders its children only for a signed-in admin.
 *
 * Like RequireAuth, **this is not a security boundary** — the admin API enforces
 * the check on every request and returns 403 to anyone else. This only decides
 * what to show, so a customer who types /admin lands somewhere sensible instead
 * of on a wall of failed requests.
 */

import type { ReactNode } from 'react'
import { Navigate } from 'react-router-dom'

import { useAuth } from './AuthContext'

export function RequireAdmin({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth()

  if (loading) return null
  if (!user) return <Navigate to="/autentificare" replace />
  // A signed-in non-admin is sent to the catalog, not the login page — they are
  // authenticated, just not authorised.
  if (!user.is_admin) return <Navigate to="/catalog" replace />

  return <>{children}</>
}

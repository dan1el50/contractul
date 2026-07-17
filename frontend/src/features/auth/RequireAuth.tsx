/**
 * Redirects signed-out visitors to the login page.
 *
 * **This is not a security boundary.** It decides what to render, nothing more.
 * Anyone can edit the bundle, or call the API directly and never load this code
 * at all — so every rule that actually matters is enforced server-side. This
 * exists so a signed-out visitor sees a login form instead of an empty screen
 * full of failed requests.
 */

import type { ReactNode } from 'react'
import { Navigate } from 'react-router-dom'

import { useAuth } from './AuthContext'

export function RequireAuth({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth()

  // Wait for the session check to settle. Redirecting during it would bounce
  // an already-signed-in user to the login page on every page load, because
  // "not loaded yet" and "not signed in" look identical from here.
  if (loading) return null

  if (!user) return <Navigate to="/autentificare" replace />

  return <>{children}</>
}

/**
 * Who is signed in.
 *
 * The frontend never decides whether you are authenticated — the API does, and
 * this only caches the answer for rendering. Any "isLoggedIn" flag kept here is
 * a convenience for the UI, never a security boundary: the server re-checks
 * every request regardless of what this file believes.
 */

import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from 'react'

import { ApiError } from '@/lib/api-client'

import * as authApi from './api'
import type { LoginInput, RegisterInput, User } from './api'

interface AuthState {
  user: User | null
  /** True until the initial "am I signed in?" check settles. */
  loading: boolean
  login: (input: LoginInput) => Promise<void>
  register: (input: RegisterInput) => Promise<void>
  logout: () => Promise<void>
  /** Re-read the signed-in user from the API, e.g. after editing the profile. */
  refresh: () => Promise<void>
}

const AuthContext = createContext<AuthState | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)

  // On boot, ask the API who we are. The cookie may still be valid from a
  // previous visit — the only way to find out is to ask, since JavaScript
  // cannot read an httpOnly cookie.
  useEffect(() => {
    let cancelled = false

    authApi
      .fetchCurrentUser()
      .then((me) => {
        if (!cancelled) setUser(me)
      })
      .catch((error: unknown) => {
        // A 401 here is the normal "not signed in" answer, not a failure.
        // Anything else is worth surfacing rather than swallowing.
        if (!(error instanceof ApiError) || error.status !== 401) {
          console.error('Unexpected error resolving session', error)
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })

    return () => {
      cancelled = true
    }
  }, [])

  const login = useCallback(async (input: LoginInput) => {
    setUser(await authApi.login(input))
  }, [])

  const register = useCallback(async (input: RegisterInput) => {
    setUser(await authApi.register(input))
  }, [])

  const logout = useCallback(async () => {
    try {
      await authApi.logout()
    } finally {
      // Cleared even if the request failed. Leaving someone looking signed in
      // after they clicked "sign out" is worse than a lost round trip — and
      // the cookie is the real session anyway.
      setUser(null)
    }
  }, [])

  const refresh = useCallback(async () => {
    setUser(await authApi.fetchCurrentUser())
  }, [])

  return (
    <AuthContext.Provider value={{ user, loading, login, register, logout, refresh }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth(): AuthState {
  const context = useContext(AuthContext)
  if (!context) throw new Error('useAuth must be used inside <AuthProvider>')
  return context
}

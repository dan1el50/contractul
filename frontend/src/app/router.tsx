/**
 * Routes.
 *
 * Thin for now — the app has two screens. Phase 4 brings the catalog, the app
 * shell, and the rest of the customer area.
 */

import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'

import { AuthPage } from '@/features/auth/AuthPage'
import { RequireAuth } from '@/features/auth/RequireAuth'
import { HomePage } from '@/features/home/HomePage'

export function Router() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/autentificare" element={<AuthPage />} />
        <Route
          path="/"
          element={
            <RequireAuth>
              <HomePage />
            </RequireAuth>
          }
        />
        {/* Unknown paths go home; RequireAuth then decides. */}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  )
}

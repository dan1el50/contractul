/**
 * Routes.
 *
 * The catalog is behind RequireAuth for now. The API serves it publicly — you
 * do not need an account to browse a shop — but the public Landing page is not
 * built yet, so there is nowhere for a signed-out visitor to land. Phase 4's
 * Landing work moves this.
 */

import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'

import { AuthPage } from '@/features/auth/AuthPage'
import { RequireAuth } from '@/features/auth/RequireAuth'
import { CatalogPage } from '@/features/catalog/CatalogPage'
import { TemplateDetailPage } from '@/features/catalog/TemplateDetailPage'
import { AddCardPage } from '@/features/wallet/AddCardPage'
import { WalletPage } from '@/features/wallet/WalletPage'

export function Router() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/autentificare" element={<AuthPage />} />
        <Route
          path="/"
          element={
            <RequireAuth>
              <CatalogPage />
            </RequireAuth>
          }
        />
        <Route
          path="/contract/:slug"
          element={
            <RequireAuth>
              <TemplateDetailPage />
            </RequireAuth>
          }
        />
        <Route
          path="/portofel"
          element={
            <RequireAuth>
              <WalletPage />
            </RequireAuth>
          }
        />
        <Route
          path="/portofel/card-nou"
          element={
            <RequireAuth>
              <AddCardPage />
            </RequireAuth>
          }
        />
        {/* Unknown paths go home; RequireAuth then decides. */}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  )
}

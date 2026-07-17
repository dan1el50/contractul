/**
 * Routes.
 *
 * The public site — Landing, catalog, and contract detail — is open to anyone,
 * because a shop you must log in to browse is a shop nobody browses. The API
 * serves these publicly too. The wallet is per-user, so it stays behind
 * RequireAuth. RequireAuth is a convenience, not a security boundary; every
 * rule that matters is enforced server-side.
 */

import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'

import { AdminPage } from '@/features/admin/AdminPage'
import { AuthPage } from '@/features/auth/AuthPage'
import { RequireAdmin } from '@/features/auth/RequireAdmin'
import { RequireAuth } from '@/features/auth/RequireAuth'
import { CartPage } from '@/features/cart/CartPage'
import { ConfirmationPage } from '@/features/cart/ConfirmationPage'
import { CatalogPage } from '@/features/catalog/CatalogPage'
import { TemplateDetailPage } from '@/features/catalog/TemplateDetailPage'
import { DocumentsPage } from '@/features/documents/DocumentsPage'
import { LandingPage } from '@/features/marketing/LandingPage'
import { SettingsPage } from '@/features/settings/SettingsPage'
import { AddCardPage } from '@/features/wallet/AddCardPage'
import { WalletPage } from '@/features/wallet/WalletPage'

export function Router() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<LandingPage />} />
        <Route path="/autentificare" element={<AuthPage />} />
        <Route path="/catalog" element={<CatalogPage />} />
        <Route path="/contract/:slug" element={<TemplateDetailPage />} />
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
        <Route
          path="/documentele-mele"
          element={
            <RequireAuth>
              <DocumentsPage />
            </RequireAuth>
          }
        />
        <Route
          path="/cos"
          element={
            <RequireAuth>
              <CartPage />
            </RequireAuth>
          }
        />
        <Route
          path="/comanda/:orderId"
          element={
            <RequireAuth>
              <ConfirmationPage />
            </RequireAuth>
          }
        />
        <Route
          path="/setari"
          element={
            <RequireAuth>
              <SettingsPage />
            </RequireAuth>
          }
        />
        <Route
          path="/admin"
          element={
            <RequireAdmin>
              <AdminPage />
            </RequireAdmin>
          }
        />
        {/* Unknown paths go to the public landing page. */}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  )
}

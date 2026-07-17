import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'

import { Router } from '@/app/router'
import { AuthProvider } from '@/features/auth/AuthContext'
import { CartProvider } from '@/features/cart/CartContext'
import '@/styles/global.css'

const container = document.getElementById('root')
if (!container) throw new Error('Root element #root not found in index.html')

// CartProvider inside AuthProvider: the cart is per-user, so it needs to know
// who is signed in and must reset when that changes.
createRoot(container).render(
  <StrictMode>
    <AuthProvider>
      <CartProvider>
        <Router />
      </CartProvider>
    </AuthProvider>
  </StrictMode>,
)

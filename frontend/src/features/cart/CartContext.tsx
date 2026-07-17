/**
 * Cart state, shared across the app.
 *
 * The sidebar badge, the contract detail page's "add" button, and the cart
 * page all read the same cart from here, so a change in one is reflected in the
 * others without prop-drilling or divergent copies. The server is the source of
 * truth; this only mirrors it and refetches.
 */

import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from 'react'

import { useAuth } from '@/features/auth/AuthContext'

import { addToCart, fetchCart, removeFromCart, type Cart } from './api'

interface CartState {
  cart: Cart | null
  count: number
  add: (slug: string) => Promise<Cart>
  remove: (templateId: string) => Promise<void>
  refresh: () => Promise<void>
}

const CartContext = createContext<CartState | null>(null)

export function CartProvider({ children }: { children: ReactNode }) {
  const { user } = useAuth()
  const [cart, setCart] = useState<Cart | null>(null)

  const refresh = useCallback(async () => {
    if (!user) {
      setCart(null)
      return
    }
    setCart(await fetchCart())
  }, [user])

  // Load on sign-in, clear on sign-out. The dependency on `user` means a
  // logout empties the badge immediately rather than leaving a stale count.
  useEffect(() => {
    void refresh().catch(() => setCart(null))
  }, [refresh])

  const add = useCallback(async (slug: string) => {
    const updated = await addToCart(slug)
    setCart(updated)
    return updated
  }, [])

  const remove = useCallback(async (templateId: string) => {
    await removeFromCart(templateId)
    setCart(await fetchCart())
  }, [])

  return (
    <CartContext.Provider value={{ cart, count: cart?.item_count ?? 0, add, remove, refresh }}>
      {children}
    </CartContext.Provider>
  )
}

export function useCart(): CartState {
  const context = useContext(CartContext)
  if (!context) throw new Error('useCart must be used inside <CartProvider>')
  return context
}

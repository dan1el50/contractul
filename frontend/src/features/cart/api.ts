import { apiGet, apiSend } from '@/lib/api-client'

export interface CartItem {
  template_id: string
  slug: string
  name: string
  category_name: string
  languages: string[]
  price_bani: number
  /** Formatted by the API — "900". Money is never divided in the frontend. */
  price_mdl: string
}

export interface Cart {
  items: CartItem[]
  item_count: number
  total_bani: number
  total_mdl: string
  /** VAT is derived by the API for display and adds back to the total. */
  net_mdl: string
  vat_mdl: string
}

export interface OrderItem {
  template_id: string
  name_snapshot: string
  unit_price_bani: number
  unit_price_mdl: string
}

export interface Order {
  id: string
  number: string
  status: string
  payment_method: string
  total_bani: number
  total_mdl: string
  net_mdl: string
  vat_mdl: string
  created_at: string
  paid_at: string | null
  items: OrderItem[]
}

export function fetchCart(): Promise<Cart> {
  return apiGet<Cart>('/cart')
}

/** Returns the whole cart, so callers do not need a second round-trip. */
export function addToCart(slug: string): Promise<Cart> {
  return apiSend<Cart>('POST', '/cart/items', { slug })
}

export function removeFromCart(templateId: string): Promise<void> {
  return apiSend<void>('DELETE', `/cart/items/${templateId}`)
}

export function checkout(): Promise<Order> {
  return apiSend<Order>('POST', '/orders', { payment_method: 'wallet' })
}

export function fetchOrder(orderId: string): Promise<Order> {
  return apiGet<Order>(`/orders/${orderId}`)
}

/**
 * The wallet balance, read here so the cart can tell whether a purchase is
 * affordable without importing the wallet feature — features do not reach into
 * each other. The one endpoint is cheap to name twice.
 */
export function fetchWalletBalance(): Promise<{ balance_bani: number; balance_mdl: string }> {
  return apiGet<{ balance_bani: number; balance_mdl: string }>('/wallet/balance')
}

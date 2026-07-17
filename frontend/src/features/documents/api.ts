import { apiGet } from '@/lib/api-client'

export interface PurchasedItem {
  template_id: string
  name_snapshot: string
  unit_price_mdl: string
}

export interface PurchaseOrder {
  id: string
  number: string
  status: string
  created_at: string
  paid_at: string | null
  items: PurchasedItem[]
}

/**
 * The user's own orders. "Documentele mele" is derived from these — every
 * purchased line is a document the user owns. Read here rather than importing
 * the cart feature, so the two stay independent.
 */
export function fetchMyOrders(): Promise<PurchaseOrder[]> {
  return apiGet<PurchaseOrder[]>('/orders')
}

import { apiGet, apiSend } from '@/lib/api-client'

export interface Balance {
  balance_bani: number
  /** Formatted by the API — "3 300". Money is never divided in the frontend. */
  balance_mdl: string
}

export interface Transaction {
  id: string
  amount_bani: number
  kind: 'topup' | 'purchase' | 'refund' | 'adjustment'
  description: string
  created_at: string
  /** Signed and formatted: "+ 3 300" / "− 900". */
  amount_mdl: string
}

export interface Card {
  id: string
  brand: string
  last4: string
  exp_month: number
  exp_year: number
  is_default: boolean
}

export interface AddCardInput {
  number: string
  exp_month: number
  exp_year: number
  cvv: string
  make_default?: boolean
}

export function fetchBalance(): Promise<Balance> {
  return apiGet<Balance>('/wallet/balance')
}

export function fetchTransactions(): Promise<Transaction[]> {
  return apiGet<Transaction[]>('/wallet/transactions')
}

export function fetchCards(): Promise<Card[]> {
  return apiGet<Card[]>('/wallet/cards')
}

/**
 * Send card details to our server to be tokenised.
 *
 * **Development only.** A real acquirer gives the browser a hosted field, and
 * the card number goes straight from the customer to them — our backend never
 * sees it, which is what keeps us out of PCI-DSS scope. This exists because the
 * mock provider has no hosted field to embed. When a real provider lands, this
 * function does not get rewritten; it disappears.
 */
export function addCard(input: AddCardInput): Promise<Card> {
  return apiSend<Card>('POST', '/wallet/cards', input)
}

export function deleteCard(cardId: string): Promise<void> {
  return apiSend<void>('DELETE', `/wallet/cards/${cardId}`)
}

export function setDefaultCard(cardId: string): Promise<Card> {
  return apiSend<Card>('POST', `/wallet/cards/${cardId}/default`)
}

export function topUp(cardId: string, amountBani: number): Promise<Transaction> {
  return apiSend<Transaction>('POST', '/wallet/top-up', {
    card_id: cardId,
    amount_bani: amountBani,
  })
}

import type { User } from '@/features/auth/api'
import { apiGet, apiSend } from '@/lib/api-client'

export interface Company {
  id: string
  name: string
  idno: string
  legal_address: string | null
  iban: string | null
  bank_name: string | null
}

export interface CompanyInput {
  name: string
  idno: string
  legal_address?: string | null
  iban?: string | null
  bank_name?: string | null
}

export interface SavedCard {
  id: string
  brand: string
  last4: string
  exp_month: number
  exp_year: number
  is_default: boolean
}

export function updateProfile(input: { full_name: string; phone: string | null }): Promise<User> {
  return apiSend<User>('PATCH', '/settings/profile', input)
}

export function changePassword(input: {
  current_password: string
  new_password: string
}): Promise<void> {
  return apiSend<void>('POST', '/settings/password', input)
}

export function fetchCompany(): Promise<Company | null> {
  return apiGet<Company | null>('/settings/company')
}

export function saveCompany(input: CompanyInput): Promise<Company> {
  return apiSend<Company>('PUT', '/settings/company', input)
}

/**
 * Saved cards, read from the wallet endpoint. The settings screen only lists
 * them and links to the wallet to add or manage — so it reads that one endpoint
 * directly rather than importing the wallet feature.
 */
export function fetchCards(): Promise<SavedCard[]> {
  return apiGet<SavedCard[]>('/wallet/cards')
}

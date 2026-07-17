import { ApiError, apiGet, apiSend } from '@/lib/api-client'

const API_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

export interface Category {
  id: string
  slug: string
  name: string
}

export interface AdminStats {
  revenue_bani: number
  revenue_mdl: string
  paid_orders: number
  users: number
  published_templates: number
}

export interface MonthRevenue {
  label: string
  revenue_bani: number
  revenue_mdl: string
}

export interface AdminOrder {
  number: string
  client_name: string
  client_email: string
  first_item: string
  item_count: number
  total_bani: number
  total_mdl: string
  status: string
  created_at: string
}

export interface AdminTemplate {
  id: string
  slug: string
  name: string
  category_name: string
  price_bani: number
  price_mdl: string
  is_published: boolean
}

export function fetchStats(): Promise<AdminStats> {
  return apiGet<AdminStats>('/admin/stats')
}

export function fetchRevenue(): Promise<MonthRevenue[]> {
  return apiGet<MonthRevenue[]>('/admin/revenue')
}

export function fetchOrders(): Promise<AdminOrder[]> {
  return apiGet<AdminOrder[]>('/admin/orders')
}

export function fetchTemplates(): Promise<AdminTemplate[]> {
  return apiGet<AdminTemplate[]>('/admin/templates')
}

export function setPublished(id: string, isPublished: boolean): Promise<AdminTemplate> {
  return apiSend<AdminTemplate>('PATCH', `/admin/templates/${id}`, { is_published: isPublished })
}

export function fetchCategories(): Promise<Category[]> {
  return apiGet<Category[]>('/categories')
}

export interface NewTemplate {
  name: string
  categoryId: string
  description: string
  priceBani: number
  languages: string[]
  isPublished: boolean
  file: File
}

/**
 * Upload a .docx and create a template. Multipart, so it bypasses the JSON
 * client — the browser must set its own multipart boundary, which means no
 * Content-Type header of ours.
 */
export async function createTemplate(input: NewTemplate): Promise<AdminTemplate> {
  const form = new FormData()
  form.append('name', input.name)
  form.append('category_id', input.categoryId)
  form.append('description', input.description)
  form.append('price_bani', String(input.priceBani))
  form.append('languages', input.languages.join(','))
  form.append('is_published', String(input.isPublished))
  form.append('file', input.file)

  const response = await fetch(`${API_URL}/api/v1/admin/templates`, {
    method: 'POST',
    credentials: 'include',
    body: form,
  })
  const body: unknown = await response.json().catch(() => null)
  if (!response.ok) {
    const detail =
      typeof body === 'object' && body !== null && 'detail' in body
        ? String((body as { detail: unknown }).detail)
        : 'Nu am putut adăuga șablonul.'
    throw new ApiError(detail, response.status, body)
  }
  return body as AdminTemplate
}

export function deleteTemplate(id: string): Promise<void> {
  return apiSend<void>('DELETE', `/admin/templates/${id}`)
}

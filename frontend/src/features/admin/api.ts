import { apiGet, apiSend } from '@/lib/api-client'

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

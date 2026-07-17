import { apiGet } from '@/lib/api-client'

export interface Category {
  id: string
  slug: string
  name: string
  description: string | null
}

export interface TemplateSummary {
  id: string
  slug: string
  name: string
  description: string
  price_bani: number
  /** Already formatted by the API — "900". Money is not divided here. */
  price_mdl: string
  languages: string[]
  category: Category
}

export interface TemplateDetail extends TemplateSummary {
  page_count: number
  free_pages: number
}

export function fetchCategories(): Promise<Category[]> {
  return apiGet<Category[]>('/categories')
}

export function fetchTemplates(categorySlug?: string): Promise<TemplateSummary[]> {
  const query = categorySlug ? `?category=${encodeURIComponent(categorySlug)}` : ''
  return apiGet<TemplateSummary[]>(`/templates${query}`)
}

export function fetchTemplate(slug: string): Promise<TemplateDetail> {
  return apiGet<TemplateDetail>(`/templates/${encodeURIComponent(slug)}`)
}

/**
 * URL of a rendered preview page.
 *
 * Pages past `free_pages` come back too small to read — the API decides that
 * from the page number, and there is no parameter to ask for more. The blur
 * applied in CSS is decoration on top of an image that is already safe.
 */
export function previewUrl(slug: string, page: number): string {
  const base = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'
  return `${base}/api/v1/templates/${encodeURIComponent(slug)}/preview/${page}`
}

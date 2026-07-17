import { apiGet } from '@/lib/api-client'

export interface DatabaseHealth {
  connected: boolean
  migration_revision: string | null
  error: string | null
}

export interface Health {
  status: 'ok' | 'degraded'
  service: string
  version: string
  environment: string
  database: DatabaseHealth
}

export function fetchHealth(): Promise<Health> {
  // A degraded backend answers 503 with a body explaining why — that body is
  // the whole point of asking, so we read it instead of throwing it away.
  return apiGet<Health>('/health', { allowErrorStatus: true })
}

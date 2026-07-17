/**
 * Auth API calls.
 *
 * There is no token handling here, and that is the point. The session lives in
 * an httpOnly cookie the browser attaches automatically and JavaScript cannot
 * read — so an XSS bug cannot steal it. The cost is that every request must opt
 * into sending cookies; see `credentials` in lib/api-client.ts.
 */

import { apiGet, apiSend } from '@/lib/api-client'

export interface User {
  id: string
  email: string
  full_name: string
  phone: string | null
  is_admin: boolean
}

export interface RegisterInput {
  email: string
  password: string
  full_name: string
  phone?: string
}

export interface LoginInput {
  email: string
  password: string
}

export function register(input: RegisterInput): Promise<User> {
  return apiSend<User>('POST', '/auth/register', input)
}

export function login(input: LoginInput): Promise<User> {
  return apiSend<User>('POST', '/auth/login', input)
}

export function logout(): Promise<void> {
  return apiSend<void>('POST', '/auth/logout')
}

export function fetchCurrentUser(): Promise<User> {
  return apiGet<User>('/auth/me')
}

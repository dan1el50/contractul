/**
 * HTTP client for the Contractul.md API.
 *
 * The single place the frontend talks to the backend.
 */

const API_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly body: unknown = null,
  ) {
    super(message)
    this.name = 'ApiError'
  }
}

interface RequestOptions {
  /**
   * Treat a non-2xx response as data rather than an error.
   *
   * Needed for the health endpoint, which answers 503 with a body that says
   * precisely what is wrong — exactly the information we want to show. Most
   * callers want the opposite and should leave this alone.
   */
  allowErrorStatus?: boolean
}

/**
 * Pull a human-readable message out of an error response.
 *
 * FastAPI puts a string in `detail` for HTTPException, and an array of field
 * errors there for validation failures. Rendering the array would show the
 * user `[object Object]`, so it is deliberately not used as a message.
 */
function messageFrom(body: unknown, fallback: string): string {
  if (typeof body === 'object' && body !== null && 'detail' in body) {
    const { detail } = body as { detail: unknown }
    if (typeof detail === 'string') return detail
  }
  return fallback
}

async function request<T>(
  method: string,
  path: string,
  body?: unknown,
  options: RequestOptions = {},
): Promise<T> {
  let response: Response

  try {
    response = await fetch(`${API_URL}/api/v1${path}`, {
      method,
      headers: {
        Accept: 'application/json',
        ...(body === undefined ? {} : { 'Content-Type': 'application/json' }),
      },
      // Without this the session cookie is neither sent nor stored, because the
      // API is a different origin (:8000) from the app (:5173). Every
      // authenticated request would silently look logged out.
      credentials: 'include',
      ...(body === undefined ? {} : { body: JSON.stringify(body) }),
    })
  } catch (cause) {
    // fetch only rejects when the request never completed — the network is
    // down, DNS failed, CORS blocked it. A 500 is a resolved promise.
    throw new ApiError(`Cannot reach the API at ${API_URL}. Is the backend running?`, 0, cause)
  }

  // 204 has no body, and calling .json() on it throws.
  const parsed: unknown =
    response.status === 204 ? null : await response.json().catch(() => null)

  if (!response.ok && !options.allowErrorStatus) {
    throw new ApiError(
      messageFrom(parsed, `Request to ${path} failed`),
      response.status,
      parsed,
    )
  }

  return parsed as T
}

export function apiGet<T>(path: string, options: RequestOptions = {}): Promise<T> {
  return request<T>('GET', path, undefined, options)
}

export function apiSend<T>(
  method: 'POST' | 'PUT' | 'PATCH' | 'DELETE',
  path: string,
  body?: unknown,
): Promise<T> {
  return request<T>(method, path, body)
}

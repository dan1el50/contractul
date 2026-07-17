/**
 * HTTP client for the Contracte.md API.
 *
 * The single place the frontend talks to the backend. Auth headers and error
 * normalisation land here in phase 3 rather than being scattered across
 * features.
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

export async function apiGet<T>(path: string, options: RequestOptions = {}): Promise<T> {
  let response: Response

  try {
    response = await fetch(`${API_URL}/api/v1${path}`, {
      headers: { Accept: 'application/json' },
    })
  } catch (cause) {
    // fetch only rejects when the request never completed — the network is
    // down, DNS failed, CORS blocked it. A 500 is a resolved promise.
    throw new ApiError(
      `Cannot reach the API at ${API_URL}. Is the backend running?`,
      0,
      cause,
    )
  }

  const body: unknown = await response.json().catch(() => null)

  if (!response.ok && !options.allowErrorStatus) {
    throw new ApiError(`Request to ${path} failed`, response.status, body)
  }

  return body as T
}

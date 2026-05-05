/**
 * Typed client for the AI Business Workflow Automator FastAPI backend.
 *
 * In dev, requests go to /api/* which Next.js rewrites to the API
 * host (see next.config.ts). In prod they're rewritten to
 * NEXT_PUBLIC_API_URL the same way.
 */

const API_BASE = '/api'

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly body?: unknown,
  ) {
    super(message)
    this.name = 'ApiError'
  }
}

async function request<T>(
  path: string,
  init: RequestInit = {},
): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...init.headers,
    },
  })

  if (!res.ok) {
    let body: unknown
    try { body = await res.json() } catch { /* response was not JSON */ }
    throw new ApiError(`${res.status} ${res.statusText}`, res.status, body)
  }

  return res.json() as Promise<T>
}

// ─── Types ───────────────────────────────────────────────────────

export interface HealthResponse {
  status: 'ok'
  db: 'ok' | 'unreachable'
}

// ─── Endpoints ────────────────────────────────────────────────────

export const api = {
  health: () => request<HealthResponse>('/health'),
}

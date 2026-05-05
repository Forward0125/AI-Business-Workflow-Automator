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
    headers: { 'Content-Type': 'application/json', ...init.headers },
  })
  if (!res.ok) {
    let body: unknown
    try { body = await res.json() } catch { /* not JSON */ }
    throw new ApiError(`${res.status} ${res.statusText}`, res.status, body)
  }
  return res.json() as Promise<T>
}

// ─── Health ──────────────────────────────────────────────────────

export interface HealthResponse {
  status: 'ok'
  db: 'ok' | 'unreachable'
}

// ─── Workflow types ──────────────────────────────────────────────

export type Tone = 'technical' | 'executive' | 'casual'

export type StepName =
  | 'fetch'
  | 'web_search'
  | 'research'
  | 'qualify'
  | 'personalize'
  | 'crm'
  | 'calendar'
  | 'email'

export type StepStatus = 'queued' | 'running' | 'success' | 'failed' | 'cancelled'
export type RunStatus  = StepStatus

export interface NewsItem  { title: string;  url: string | null; summary: string | null }
export interface PersonRef { name: string;   role: string | null }

/** Metadata shape per step. All optional because they only appear on
 *  ``step.completed`` events (and inside ``snapshot.run.steps[].metadata``). */
export interface StepMeta {
  // fetch
  lead_id?:       number
  domain?:        string
  fetched_bytes?: number
  elapsed_ms?:    number
  title?:         string
  // web_search
  hits?: number
  // research
  industry?:    string | null
  size?:        string | null
  headline?:    string | null
  summary?:     string | null
  tech_stack?:  string[]
  key_people?:  PersonRef[]
  recent_news?: NewsItem[]
  // qualify
  composite?: number
  qualified?: boolean
  budget?:    number
  authority?: number
  need?:      number
  timing?:    number
  // personalize
  email_draft_id?:    number
  tone?:              Tone
  subject?:           string
  body?:              string
  cited_findings?:    string[]
  unknown_citations?: string[]
  // mocked actions (crm/calendar/email)
  duration_ms?:  number
  platform?:     string
  deal_stage?:   string
  score?:        number
  scheduled_at?: string
  message_id?:   string
  payload?:      Record<string, unknown>
  // common
  tokens_in?:  number
  tokens_out?: number
  cost_usd?:   number
}

export interface StepInfo {
  name:         StepName
  status:       StepStatus
  progress_pct: number
  started_at:   string | null
  finished_at:  string | null
  metadata:     StepMeta | null
}

export interface RunInfo {
  id:                number
  lead_id:           number | null
  status:            RunStatus
  triggered_by:      string | null
  started_at:        string | null
  finished_at:       string | null
  total_cost_usd:    number | null
  total_tokens_in:   number
  total_tokens_out:  number
  error_message:     string | null
  steps:             StepInfo[]
}

// ─── SSE event types ─────────────────────────────────────────────

interface SnapshotEvent      { type: 'snapshot';  run: RunInfo }
interface RunStartedEvent    { type: 'run.started';  run_id: number; url: string; tone: Tone }
interface StepStartedEvent   { type: 'step.started'; step: StepName }
interface StepCompletedEvent extends StepMeta {
  type: 'step.completed'
  step: StepName
}
interface StepFailedEvent    { type: 'step.failed';  step: StepName; error: string }
interface RunCompletedEvent {
  type: 'run.completed'
  run_id: number
  lead_id: number
  qualified: boolean
  composite: number
  email_subject: string
  total_cost_usd: number
  total_tokens_in: number
  total_tokens_out: number
}
interface RunFailedEvent     { type: 'run.failed'; run_id: number; error: string }
interface StreamEndEvent     { type: 'stream.end' }

export type WorkflowEvent =
  | SnapshotEvent
  | RunStartedEvent
  | StepStartedEvent
  | StepCompletedEvent
  | StepFailedEvent
  | RunCompletedEvent
  | RunFailedEvent
  | StreamEndEvent

// ─── Dashboard ───────────────────────────────────────────────────

export interface KPIs {
  leads_24h:      number
  leads_total:    number
  runs_total:     number
  runs_last_7d:   number
  active_runs:    number
  avg_cost_usd:   number | null
  qualified_rate: number | null
}

export interface TimeseriesPoint {
  day:       string
  runs:      number
  qualified: number
  avg_cost:  number | null
}

export interface TopLead {
  lead_id:        number
  domain:         string | null
  industry:       string | null
  input_url:      string
  run_id:         number | null
  run_status:     string | null
  qualified:      boolean | null
  composite:      number | null
  email_subject:  string | null
  created_at:     string | null
}

export type AlertSeverity = 'info' | 'warning' | 'error'

export interface AlertRow {
  id:         number
  severity:   AlertSeverity
  title:      string
  body:       string | null
  source:     string | null
  created_at: string | null
}

export interface DashboardSummary {
  kpis:       KPIs
  timeseries: TimeseriesPoint[]
  top_leads:  TopLead[]
  alerts:     AlertRow[]
}

// ─── Endpoints ───────────────────────────────────────────────────

export interface CreateRunBody {
  url:    string
  tone?:  Tone
  pitch?: string
}

export interface CreateRunResponse { run_id: number }

export const api = {
  health: () => request<HealthResponse>('/health'),

  createWorkflowRun: (body: CreateRunBody) =>
    request<CreateRunResponse>('/workflows/runs', {
      method: 'POST',
      body:   JSON.stringify(body),
    }),

  getWorkflowRun: (runId: number) =>
    request<RunInfo>(`/workflows/runs/${runId}`),

  dashboardSummary: () => request<DashboardSummary>('/dashboard/summary'),

  /** Async-iterable over typed workflow events. */
  async *streamWorkflowRun(
    runId: number,
    opts: { signal?: AbortSignal } = {},
  ): AsyncGenerator<WorkflowEvent, void, unknown> {
    const res = await fetch(`${API_BASE}/workflows/runs/${runId}/events`, {
      method: 'GET',
      signal: opts.signal,
    })
    if (!res.ok || !res.body) {
      throw new ApiError(`${res.status} ${res.statusText}`, res.status)
    }
    const reader  = res.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''
    try {
      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        const events = buffer.split('\n\n')
        buffer = events.pop() ?? ''
        for (const raw of events) {
          if (!raw.trim()) continue
          let data = ''
          for (const line of raw.split('\n')) {
            if (line.startsWith('data: ')) data += line.slice(6)
          }
          if (!data) continue
          try { yield JSON.parse(data) as WorkflowEvent } catch { /* malformed */ }
        }
      }
    } finally {
      reader.releaseLock()
    }
  },
}

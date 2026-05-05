'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import {
  api,
  ApiError,
  type StepInfo,
  type StepName,
  type Tone,
  type WorkflowEvent,
} from '@/lib/api'
import { LeadInput } from '@/components/lead/LeadInput'
import { WorkflowDAG } from '@/components/lead/WorkflowDAG'
import { ResearchCard } from '@/components/lead/ResearchCard'
import { QualificationCard } from '@/components/lead/QualificationCard'
import { EmailDraftCard } from '@/components/lead/EmailDraftCard'
import { MockedActionsPanel } from '@/components/lead/MockedActionsPanel'


type StepMap = Partial<Record<StepName, StepInfo>>

type Status = 'idle' | 'running' | 'completed' | 'error'

interface PageState {
  status:     Status
  url:        string
  tone:       Tone
  runId:      number | null
  steps:      StepMap
  totals:     { cost?: number; tokens_in?: number; tokens_out?: number }
  qualified:  boolean | null
  errorText:  string | null
}

const INITIAL: PageState = {
  status:     'idle',
  url:        '',
  tone:       'executive',
  runId:      null,
  steps:      {},
  totals:     {},
  qualified:  null,
  errorText:  null,
}


export default function LeadPage() {
  const [state, setState] = useState<PageState>(INITIAL)
  const abortRef = useRef<AbortController | null>(null)

  // Cleanup any open SSE on unmount.
  useEffect(() => () => abortRef.current?.abort(), [])

  const onSubmit = useCallback(async (url: string, tone: Tone) => {
    abortRef.current?.abort()
    const ac = new AbortController()
    abortRef.current = ac

    setState({ ...INITIAL, status: 'running', url, tone })

    let runId: number
    try {
      const res = await api.createWorkflowRun({ url, tone })
      runId = res.run_id
    } catch (err) {
      const msg = err instanceof ApiError
        ? `${err.status} — ${err.message}`
        : err instanceof Error ? err.message : 'unknown error'
      setState((s) => ({ ...s, status: 'error', errorText: msg }))
      return
    }

    setState((s) => ({ ...s, runId }))

    try {
      for await (const ev of api.streamWorkflowRun(runId, { signal: ac.signal })) {
        if (ac.signal.aborted) return
        setState((s) => reduce(s, ev))
      }
    } catch (err) {
      if (ac.signal.aborted) return
      const msg = err instanceof ApiError
        ? `${err.status} — ${err.message}`
        : err instanceof Error ? err.message : 'stream error'
      setState((s) => ({ ...s, status: 'error', errorText: msg }))
    }
  }, [])

  const isRunning   = state.status === 'running'
  const research    = state.steps.research
  const qualify     = state.steps.qualify
  const personalize = state.steps.personalize

  const researchPending    = isRunning && (!research    || research.status    !== 'success')
  const qualifyPending     = isRunning && (!qualify     || qualify.status     !== 'success')
  const personalizePending = isRunning && (!personalize || personalize.status !== 'success')

  return (
    <div className="px-6 py-8 md:py-10 space-y-6 max-w-6xl">
      <header>
        <p className="text-[11px] font-mono text-foreground-3 tracking-[0.15em] uppercase mb-2">
          Lead
        </p>
        <h1 className="font-display text-3xl md:text-4xl font-bold tracking-tight">
          Research → Qualify → Personalize.
        </h1>
        <p className="mt-2 text-[14px] text-foreground-2 max-w-2xl">
          Paste a company URL. The AI fetches the homepage, searches the
          web, scores BANT fit, and drafts a personalized email — all in
          one live workflow. Demo mode: CRM, calendar, and email sends
          are simulated.
        </p>
      </header>

      <LeadInput
        onSubmit={onSubmit}
        disabled={isRunning}
        initialTone={state.tone}
      />

      {state.errorText && (
        <div className="px-4 py-3 rounded-lg bg-amber-500/10 border border-amber-500/20 text-[13px] text-amber-400">
          {state.errorText}
        </div>
      )}

      {(isRunning || state.runId != null) && (
        <>
          <WorkflowDAG steps={state.steps} />

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <ResearchCard       meta={research?.metadata    ?? null} pending={researchPending}    />
            <QualificationCard  meta={qualify?.metadata     ?? null} pending={qualifyPending}     />
            <div className="lg:col-span-2">
              <EmailDraftCard   meta={personalize?.metadata ?? null} pending={personalizePending} />
            </div>
            <div className="lg:col-span-2">
              <MockedActionsPanel steps={state.steps} />
            </div>
          </div>
        </>
      )}

      {state.status === 'completed' && (
        <div className="flex flex-wrap gap-x-6 gap-y-1 text-[11px] font-mono text-foreground-3 pt-2 border-t border-border/6">
          {state.runId != null && <span>run #{state.runId}</span>}
          {state.totals.cost != null && <span>cost ${state.totals.cost.toFixed(4)}</span>}
          {state.totals.tokens_in != null && state.totals.tokens_out != null && (
            <span>tokens in/out {state.totals.tokens_in}/{state.totals.tokens_out}</span>
          )}
          {state.qualified != null && (
            <span className={state.qualified ? 'text-emerald-400' : 'text-amber-400'}>
              {state.qualified ? 'qualified' : 'not qualified'}
            </span>
          )}
        </div>
      )}
    </div>
  )
}


/* ─── Reducer for SSE events ────────────────────────────────── */

function reduce(s: PageState, ev: WorkflowEvent): PageState {
  switch (ev.type) {
    case 'snapshot': {
      const steps: StepMap = {}
      for (const step of ev.run.steps) steps[step.name] = step
      return { ...s, runId: ev.run.id, steps }
    }
    case 'run.started':
      return s
    case 'step.started':
      return {
        ...s,
        steps: {
          ...s.steps,
          [ev.step]: {
            name:        ev.step,
            status:      'running',
            progress_pct: 0,
            started_at:  new Date().toISOString(),
            finished_at: null,
            metadata:    s.steps[ev.step]?.metadata ?? null,
          } as StepInfo,
        },
      }
    case 'step.completed': {
      // Drop the `type` and `step` fields; rest is the metadata payload.
      const { type: _t, step: _s, ...meta } = ev
      void _t; void _s
      return {
        ...s,
        steps: {
          ...s.steps,
          [ev.step]: {
            name:         ev.step,
            status:       'success',
            progress_pct: 100,
            started_at:   s.steps[ev.step]?.started_at ?? null,
            finished_at:  new Date().toISOString(),
            metadata:     meta,
          },
        },
      }
    }
    case 'step.failed':
      return {
        ...s,
        steps: {
          ...s.steps,
          [ev.step]: {
            name:         ev.step,
            status:       'failed',
            progress_pct: 0,
            started_at:   s.steps[ev.step]?.started_at ?? null,
            finished_at:  new Date().toISOString(),
            metadata:     s.steps[ev.step]?.metadata ?? null,
          },
        },
      }
    case 'run.completed':
      return {
        ...s,
        status:    'completed',
        qualified: ev.qualified,
        totals: {
          cost:       ev.total_cost_usd,
          tokens_in:  ev.total_tokens_in,
          tokens_out: ev.total_tokens_out,
        },
      }
    case 'run.failed':
      return { ...s, status: 'error', errorText: ev.error }
    case 'stream.end':
      return s
    default:
      return s
  }
}

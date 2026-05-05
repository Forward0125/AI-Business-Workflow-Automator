'use client'

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { RefreshCw, Workflow as WorkflowIcon } from 'lucide-react'
import {
  api,
  type RunStatus,
  type StepInfo,
  type StepName,
  type WorkflowEvent,
  type WorkflowRunListItem,
} from '@/lib/api'
import { cn } from '@/lib/utils'
import { WorkflowDAG } from '@/components/lead/WorkflowDAG'
import { ResearchCard } from '@/components/lead/ResearchCard'
import { QualificationCard } from '@/components/lead/QualificationCard'
import { EmailDraftCard } from '@/components/lead/EmailDraftCard'
import { MockedActionsPanel } from '@/components/lead/MockedActionsPanel'
import { RunsList } from '@/components/workflows/RunsList'


type StepMap = Partial<Record<StepName, StepInfo>>

type StatusFilter = RunStatus | 'all'


const FILTER_LABELS: { value: StatusFilter; label: string }[] = [
  { value: 'all',     label: 'All'     },
  { value: 'running', label: 'Running' },
  { value: 'success', label: 'Success' },
  { value: 'failed',  label: 'Failed'  },
]


export default function WorkflowsPage() {
  const [runs,         setRuns]         = useState<WorkflowRunListItem[]>([])
  const [filter,       setFilter]       = useState<StatusFilter>('all')
  const [selectedId,   setSelectedId]   = useState<number | null>(null)
  const [steps,        setSteps]        = useState<StepMap>({})
  const [refreshing,   setRefreshing]   = useState(false)
  const [error,        setError]        = useState<string | null>(null)

  const abortRef = useRef<AbortController | null>(null)

  /* ─── Load runs list ──────────────────────────────────────── */

  const loadRuns = useCallback(async () => {
    setRefreshing(true)
    try {
      const list = await api.listWorkflowRuns({ limit: 30 })
      setRuns(list)
      setError(null)
      // If nothing selected yet, pick the most recent run.
      if (list.length > 0) {
        setSelectedId((curr) => curr ?? list[0].run_id)
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'failed to load runs')
    } finally {
      setRefreshing(false)
    }
  }, [])

  useEffect(() => { loadRuns() }, [loadRuns])

  /* ─── Subscribe to selected run's SSE ─────────────────────── */

  useEffect(() => {
    if (selectedId == null) return

    abortRef.current?.abort()
    const ac = new AbortController()
    abortRef.current = ac

    setSteps({})

    ;(async () => {
      try {
        for await (const ev of api.streamWorkflowRun(selectedId, { signal: ac.signal })) {
          if (ac.signal.aborted) return
          setSteps((prev) => reduce(prev, ev))
        }
      } catch {
        /* ignore -- snapshot is enough for completed runs */
      }
    })()

    return () => ac.abort()
  }, [selectedId])

  // Cleanup any in-flight stream on unmount.
  useEffect(() => () => abortRef.current?.abort(), [])

  /* ─── Filtered list ───────────────────────────────────────── */

  const visibleRuns = useMemo(() => {
    if (filter === 'all') return runs
    return runs.filter((r) => r.status === filter)
  }, [runs, filter])

  const selectedRun = useMemo(
    () => runs.find((r) => r.run_id === selectedId) ?? null,
    [runs, selectedId],
  )

  /* ─── Derived ─────────────────────────────────────────────── */

  const research    = steps.research
  const qualify     = steps.qualify
  const personalize = steps.personalize


  /* ─── Render ──────────────────────────────────────────────── */

  return (
    <div className="grid grid-cols-1 xl:grid-cols-[200px_1fr] gap-6 px-6 py-8 md:py-10">
      {/* Sidebar filters */}
      <aside className="space-y-3">
        <p className="text-[11px] font-mono text-foreground-3 tracking-[0.15em] uppercase">
          Workflow Runs
        </p>
        {FILTER_LABELS.map(({ value, label }) => {
          const count = value === 'all'
            ? runs.length
            : runs.filter((r) => r.status === value).length
          const active = filter === value
          return (
            <button
              key={value}
              onClick={() => setFilter(value)}
              className={cn(
                'w-full flex items-center justify-between px-3 py-2 rounded-lg text-[13px]',
                'transition-colors',
                active
                  ? 'bg-surface-high text-foreground'
                  : 'text-foreground-2 hover:bg-surface-high/50 hover:text-foreground',
              )}
            >
              <span>{label}</span>
              <span className="text-[10px] font-mono text-foreground-3">{count}</span>
            </button>
          )
        })}
      </aside>

      {/* Main column */}
      <div className="min-w-0 space-y-6">
        <header className="flex items-end justify-between gap-3 flex-wrap">
          <div>
            <p className="text-[11px] font-mono text-foreground-3 tracking-[0.15em] uppercase mb-2">
              Workflows
            </p>
            <h1 className="font-display text-3xl md:text-4xl font-bold tracking-tight">
              Lead-to-conversion as a DAG.
            </h1>
            <p className="mt-2 text-[14px] text-foreground-2 max-w-2xl">
              Browse recent workflow runs. Click a row to replay its DAG
              and result cards.
            </p>
          </div>
          <button
            onClick={loadRuns}
            className={cn(
              'inline-flex items-center gap-2 px-3 py-1.5 rounded-lg',
              'text-foreground-3 hover:text-foreground hover:bg-surface-high',
              refreshing && 'text-accent-warm',
            )}
          >
            <RefreshCw size={14} className={refreshing ? 'animate-spin' : ''} />
            <span className="text-[11px] font-mono tracking-[0.15em] uppercase">
              {refreshing ? 'refreshing' : 'refresh'}
            </span>
          </button>
        </header>

        {error && (
          <div className="px-4 py-3 rounded-lg bg-amber-500/10 border border-amber-500/20 text-[13px] text-amber-400">
            {error}
          </div>
        )}

        {/* List of runs */}
        <RunsList
          runs={visibleRuns}
          selectedId={selectedId}
          onSelect={setSelectedId}
        />

        {/* Selected run detail (DAG + result cards) */}
        {selectedRun && Object.keys(steps).length > 0 && (
          <>
            <div className="flex items-center gap-2 text-[12px] text-foreground-2 px-1">
              <WorkflowIcon size={13} className="text-accent-warm" />
              <span>
                Run <span className="text-foreground font-medium">#{selectedRun.run_id}</span>
              </span>
              {selectedRun.domain && (
                <>
                  <span className="text-foreground-3">·</span>
                  <span className="font-mono">{selectedRun.domain}</span>
                </>
              )}
            </div>

            <WorkflowDAG steps={steps} />

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <ResearchCard      meta={research?.metadata    ?? null} pending={false} />
              <QualificationCard meta={qualify?.metadata     ?? null} pending={false} />
              <div className="lg:col-span-2">
                <EmailDraftCard  meta={personalize?.metadata ?? null} pending={false} />
              </div>
              <div className="lg:col-span-2">
                <MockedActionsPanel steps={steps} />
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  )
}


/* ─── Reducer (same shape as the Lead page) ─────────────────── */

function reduce(s: StepMap, ev: WorkflowEvent): StepMap {
  switch (ev.type) {
    case 'snapshot': {
      const next: StepMap = {}
      for (const step of ev.run.steps) next[step.name] = step
      return next
    }
    case 'step.started':
      return {
        ...s,
        [ev.step]: {
          name:         ev.step,
          status:       'running',
          progress_pct: 0,
          started_at:   new Date().toISOString(),
          finished_at:  null,
          metadata:     s[ev.step]?.metadata ?? null,
        },
      }
    case 'step.completed': {
      const { type: _t, step: _stp, ...meta } = ev
      void _t; void _stp
      return {
        ...s,
        [ev.step]: {
          name:         ev.step,
          status:       'success',
          progress_pct: 100,
          started_at:   s[ev.step]?.started_at ?? null,
          finished_at:  new Date().toISOString(),
          metadata:     meta,
        },
      }
    }
    case 'step.failed':
      return {
        ...s,
        [ev.step]: {
          name:         ev.step,
          status:       'failed',
          progress_pct: 0,
          started_at:   s[ev.step]?.started_at ?? null,
          finished_at:  new Date().toISOString(),
          metadata:     s[ev.step]?.metadata ?? null,
        },
      }
    default:
      return s
  }
}

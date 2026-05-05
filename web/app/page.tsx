'use client'

import { useEffect, useState } from 'react'
import { Sparkles, CheckCircle2, AlertCircle, Loader2 } from 'lucide-react'
import { api, ApiError, type HealthResponse } from '@/lib/api'
import { Container } from '@/components/ui/Container'
import { cn } from '@/lib/utils'

type HealthState =
  | { kind: 'loading' }
  | { kind: 'ok';      data: HealthResponse }
  | { kind: 'error';   message: string }

export default function LeadPage() {
  const [health, setHealth] = useState<HealthState>({ kind: 'loading' })

  useEffect(() => {
    let cancelled = false
    api.health()
      .then((data) => { if (!cancelled) setHealth({ kind: 'ok', data }) })
      .catch((err: unknown) => {
        if (cancelled) return
        const msg = err instanceof ApiError
          ? `${err.status} ${err.message}`
          : err instanceof Error ? err.message : 'unknown error'
        setHealth({ kind: 'error', message: msg })
      })
    return () => { cancelled = true }
  }, [])

  return (
    <Container size="full" className="py-8 md:py-12">
      <div className="mb-10">
        <p className="text-[11px] font-mono text-foreground-3 tracking-[0.15em] uppercase mb-3">
          Lead
        </p>
        <h1 className="font-display text-4xl md:text-5xl font-bold tracking-tight">
          Research → Qualify → Personalize.
        </h1>
        <p className="mt-3 text-foreground-2 max-w-2xl">
          Paste a company URL. The AI fetches the homepage, runs a web
          search, scores BANT fit, and drafts a personalized outreach
          email — all in one live workflow. Demo mode: CRM, calendar
          and email sends are simulated.
        </p>
      </div>

      {/* Lead form -- non-functional placeholder until step 6/11 */}
      <div className="relative mb-8 max-w-3xl">
        <Sparkles
          size={18}
          className="absolute left-4 top-1/2 -translate-y-1/2 text-foreground-3"
        />
        <input
          type="text"
          disabled
          placeholder="https://stripe.com"
          className={cn(
            'w-full pl-11 pr-4 py-3.5',
            'bg-surface border border-border/10 rounded-xl',
            'text-foreground placeholder:text-foreground-3',
            'focus:outline-none focus:border-accent-warm/40',
            'disabled:opacity-60 disabled:cursor-not-allowed',
          )}
        />
        <div className="mt-2 text-[11px] font-mono text-foreground-3">
          Lead intake arrives in step 6 — workflow viz in step 11.
        </div>
      </div>

      {/* Backend connectivity card */}
      <HealthCard state={health} />
    </Container>
  )
}

function HealthCard({ state }: { state: HealthState }) {
  return (
    <div className="max-w-md p-5 rounded-xl bg-surface border border-border/8">
      <p className="text-[11px] font-mono text-foreground-3 tracking-[0.15em] uppercase mb-3">
        Backend status
      </p>
      <div className="flex items-center gap-3">
        {state.kind === 'loading' && (
          <>
            <Loader2 size={16} className="text-foreground-3 animate-spin" />
            <span className="text-sm text-foreground-2">Pinging API…</span>
          </>
        )}
        {state.kind === 'ok' && (
          <>
            <CheckCircle2 size={16} className="text-emerald-400" />
            <span className="text-sm text-foreground">
              API reachable · DB {state.data.db}
            </span>
          </>
        )}
        {state.kind === 'error' && (
          <>
            <AlertCircle size={16} className="text-amber-400" />
            <span className="text-sm text-foreground">
              {state.message}
            </span>
          </>
        )}
      </div>
      {state.kind === 'error' && (
        <p className="mt-3 text-xs text-foreground-3 font-mono">
          Hint: is <code>uv run python run.py</code> running in <code>api/</code>?
        </p>
      )}
    </div>
  )
}

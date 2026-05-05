'use client'

import { useEffect, useState } from 'react'
import {
  Sparkles, ShieldCheck, DollarSign, Workflow, RefreshCw,
} from 'lucide-react'
import { api, type DashboardSummary } from '@/lib/api'
import { cn } from '@/lib/utils'
import { KpiCard } from '@/components/dashboard/KpiCard'
import { PerformanceChart } from '@/components/dashboard/PerformanceChart'
import { TopLeadsTable } from '@/components/dashboard/TopLeadsTable'
import { AlertsPanel } from '@/components/dashboard/AlertsPanel'


const POLL_MS = 5_000


export default function DashboardPage() {
  const [data,    setData]    = useState<DashboardSummary | null>(null)
  const [error,   setError]   = useState<string | null>(null)
  const [loaded,  setLoaded]  = useState(false)
  const [tick,    setTick]    = useState(0)
  const [refreshing, setRefreshing] = useState(false)

  useEffect(() => {
    let cancelled = false

    const run = async () => {
      setRefreshing(true)
      try {
        const next = await api.dashboardSummary()
        if (!cancelled) { setData(next); setError(null); setLoaded(true) }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'failed to load')
          setLoaded(true)
        }
      } finally {
        if (!cancelled) setRefreshing(false)
      }
    }

    run()
    const id = window.setInterval(() => setTick((n) => n + 1), POLL_MS)
    return () => { cancelled = true; window.clearInterval(id) }
  }, [tick])

  return (
    <div className="px-6 py-8 md:py-10 space-y-6 max-w-7xl">
      <header className="flex items-end justify-between gap-3 flex-wrap">
        <div>
          <p className="text-[11px] font-mono text-foreground-3 tracking-[0.15em] uppercase mb-2">
            Dashboard
          </p>
          <h1 className="font-display text-3xl md:text-4xl font-bold tracking-tight">
            Pipeline health.
          </h1>
          <p className="mt-2 text-[14px] text-foreground-2 max-w-xl">
            KPIs, qualified rate, top leads, and alerts — all from real
            workflow traffic.
          </p>
        </div>
        <button
          onClick={() => setTick((n) => n + 1)}
          className={cn(
            'inline-flex items-center gap-2 px-3 py-1.5 rounded-lg',
            'text-foreground-3 hover:text-foreground hover:bg-surface-high',
            refreshing && 'text-accent-warm',
          )}
          title={`Auto-refresh every ${POLL_MS / 1000}s`}
        >
          <RefreshCw size={14} className={refreshing ? 'animate-spin' : ''} />
          <span className="text-[11px] font-mono tracking-[0.15em] uppercase">
            {refreshing ? 'refreshing' : 'live'}
          </span>
        </button>
      </header>

      {error && (
        <div className="px-4 py-3 rounded-lg bg-amber-500/10 border border-amber-500/20 text-[13px] text-amber-400">
          {error}
        </div>
      )}

      <section className="grid gap-4 grid-cols-1 sm:grid-cols-2 lg:grid-cols-4">
        <KpiCard
          label="Leads Processed"
          icon={Sparkles}
          value={String(data?.kpis.leads_total ?? 0)}
          hint={`${data?.kpis.leads_24h ?? 0} in last 24h`}
        />
        <KpiCard
          label="Qualified Rate"
          icon={ShieldCheck}
          value={
            data?.kpis.qualified_rate != null
              ? `${(data.kpis.qualified_rate * 100).toFixed(0)}%`
              : '—'
          }
          hint="all-time qualified / total"
        />
        <KpiCard
          label="Avg Cost / Run"
          icon={DollarSign}
          value={
            data?.kpis.avg_cost_usd != null
              ? `$${data.kpis.avg_cost_usd.toFixed(4)}`
              : '—'
          }
          hint="successful runs (7d)"
        />
        <KpiCard
          label="Active Runs"
          icon={Workflow}
          value={String(data?.kpis.active_runs ?? 0)}
          hint={`${data?.kpis.runs_total ?? 0} runs total`}
        />
      </section>

      {!data && !error && (
        <div className="rounded-xl bg-surface border border-border/8 px-5 py-8 text-center text-sm text-foreground-3">
          {loaded ? 'no data yet' : 'loading…'}
        </div>
      )}

      {data && (
        <>
          <section className="grid gap-6 grid-cols-1 lg:grid-cols-[1fr_360px]">
            <PerformanceChart data={data.timeseries} />
            <AlertsPanel alerts={data.alerts} />
          </section>

          <TopLeadsTable rows={data.top_leads} />
        </>
      )}
    </div>
  )
}

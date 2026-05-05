'use client'

import { ShieldCheck, Loader2, CheckCircle2, AlertCircle } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { StepMeta } from '@/lib/api'


interface QualificationCardProps {
  meta:    StepMeta | null
  pending: boolean
}


const BANT = [
  { key: 'budget',    label: 'Budget'    },
  { key: 'authority', label: 'Authority' },
  { key: 'need',      label: 'Need'      },
  { key: 'timing',    label: 'Timing'    },
] as const


export function QualificationCard({ meta, pending }: QualificationCardProps) {
  const hasData = !!(meta && meta.composite != null)

  return (
    <div className="rounded-xl bg-surface border border-border/8 overflow-hidden">
      <header className="px-5 py-3 border-b border-border/6 flex items-center gap-2.5">
        <ShieldCheck size={15} className="text-accent-blue" />
        <h3 className="text-sm font-medium text-foreground">Qualification (BANT)</h3>
        <div className="flex-1" />
        {pending && !hasData && (
          <span className="text-[10px] font-mono text-foreground-3 tracking-[0.15em] uppercase inline-flex items-center gap-1.5">
            <Loader2 size={11} className="animate-spin" />
            scoring
          </span>
        )}
        {hasData && (
          <span className={cn(
            'inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-mono uppercase tracking-[0.12em]',
            meta!.qualified
              ? 'text-emerald-400 bg-emerald-500/10'
              : 'text-amber-400 bg-amber-500/10',
          )}>
            {meta!.qualified
              ? <><CheckCircle2 size={10} /> qualified</>
              : <><AlertCircle size={10}  /> not qualified</>}
          </span>
        )}
      </header>

      <div className="px-5 py-4 space-y-4">
        {!hasData && !pending && (
          <p className="text-[12px] text-foreground-3 text-center py-4">
            Qualification scores after research completes.
          </p>
        )}

        {hasData && (
          <>
            {/* Composite */}
            <div className="flex items-baseline gap-2 pb-3 border-b border-border/6">
              <p className="font-display text-3xl font-bold tabular-nums">
                {meta!.composite!.toFixed(2)}
              </p>
              <p className="text-[10px] font-mono text-foreground-3 tracking-[0.12em] uppercase">
                composite (mean of B/A/N/T)
              </p>
            </div>

            {/* BANT bars */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-6 gap-y-3">
              {BANT.map(({ key, label }) => {
                const v = meta?.[key as 'budget' | 'authority' | 'need' | 'timing'] ?? null
                return <ScoreRow key={key} label={label} value={v} />
              })}
            </div>

            {/* Reasoning -- not in metadata, but composite + per-axis is enough.
                We rely on the workflow_steps row also storing reasoning;
                surfacing it isn't critical for the live demo. */}
          </>
        )}
      </div>
    </div>
  )
}


function ScoreRow({ label, value }: { label: string; value: number | null }) {
  const v   = value ?? 0
  const pct = Math.round(v * 100)
  const passed = v >= 0.6
  return (
    <div>
      <div className="flex items-baseline justify-between mb-1">
        <span className="text-[12px] font-medium text-foreground-2">{label}</span>
        <span className="text-[12px] font-mono tabular-nums text-foreground">
          {value != null ? value.toFixed(2) : '—'}
        </span>
      </div>
      <div className="h-1.5 rounded-full bg-surface-high overflow-hidden">
        <div
          className={cn(
            'h-full transition-[width] duration-700 ease-out',
            passed
              ? 'bg-gradient-to-r from-accent-blue to-accent-warm'
              : 'bg-amber-500/60',
          )}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  )
}

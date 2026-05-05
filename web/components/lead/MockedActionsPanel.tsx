'use client'

import { Briefcase, Calendar, Send } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { StepInfo, StepName } from '@/lib/api'


interface MockedActionsPanelProps {
  steps: Partial<Record<StepName, StepInfo>>
}


const ACTIONS = [
  { name: 'crm'      as const, label: 'CRM Update',     icon: Briefcase },
  { name: 'calendar' as const, label: 'Calendar Slot',  icon: Calendar  },
  { name: 'email'    as const, label: 'Email Send',     icon: Send      },
]


export function MockedActionsPanel({ steps }: MockedActionsPanelProps) {
  return (
    <div className="rounded-xl bg-surface border border-border/8 overflow-hidden">
      <header className="px-5 py-3 border-b border-border/6 flex items-center gap-2.5">
        <h3 className="text-sm font-medium text-foreground">Simulated Actions</h3>
        <span className="text-[10px] font-mono text-foreground-3 tracking-[0.12em] uppercase">
          demo mode · no real API calls
        </span>
      </header>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-px bg-border/6">
        {ACTIONS.map(({ name, label, icon: Icon }) => {
          const step = steps[name]
          const meta = step?.metadata ?? null
          const status = step?.status ?? 'queued'
          const payload = (meta?.payload as Record<string, unknown> | undefined) ?? null

          return (
            <div key={name} className="bg-surface px-4 py-3">
              <div className="flex items-center gap-2 mb-2">
                <Icon size={14} className={cn(
                  status === 'success' && 'text-emerald-400',
                  status === 'running' && 'text-accent-blue',
                  status === 'queued'  && 'text-foreground-3',
                  status === 'failed'  && 'text-rose-400',
                )} />
                <p className="text-[12px] font-medium text-foreground">{label}</p>
                {meta?.duration_ms != null && (
                  <span className="ml-auto text-[10px] font-mono text-foreground-3">
                    {meta.duration_ms}ms
                  </span>
                )}
              </div>

              {meta?.platform && (
                <p className="text-[10px] font-mono text-foreground-3 mb-2">
                  {meta.platform}
                </p>
              )}

              {payload ? (
                <ActionSummary name={name} payload={payload} />
              ) : (
                <p className="text-[11px] text-foreground-3 italic">
                  {status === 'queued' ? 'pending' : 'running…'}
                </p>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}


function ActionSummary({
  name, payload,
}: { name: 'crm' | 'calendar' | 'email'; payload: Record<string, unknown> }) {
  if (name === 'crm') {
    const company = payload.company as Record<string, unknown> | undefined
    const stage   = payload.deal_stage as string | undefined
    const score   = payload.score      as number  | undefined
    return (
      <div className="text-[11px] text-foreground-2 space-y-0.5 font-mono">
        <p>contact: <span className="text-foreground">{String(payload.contact_id ?? '')}</span></p>
        {company && (
          <p>industry: <span className="text-foreground">{String(company.industry ?? '—')}</span></p>
        )}
        <p>
          stage: <span className="text-foreground">{stage ?? '—'}</span>
          {score != null && <span className="text-foreground-3"> · score {score}</span>}
        </p>
      </div>
    )
  }
  if (name === 'calendar') {
    return (
      <div className="text-[11px] text-foreground-2 space-y-0.5 font-mono">
        <p>slot: <span className="text-foreground">{fmtDate(payload.scheduled_at)}</span></p>
        <p>duration: <span className="text-foreground">{String(payload.duration_minutes ?? 30)} min</span></p>
      </div>
    )
  }
  // email
  return (
    <div className="text-[11px] text-foreground-2 space-y-0.5 font-mono">
      <p>to: <span className="text-foreground">{String(payload.to ?? '')}</span></p>
      <p>send: <span className="text-foreground">{fmtDate(payload.scheduled_at)}</span></p>
      <p>status: <span className="text-foreground">{String(payload.status ?? '')}</span></p>
    </div>
  )
}


function fmtDate(v: unknown): string {
  if (typeof v !== 'string') return '—'
  try {
    return new Date(v).toLocaleString('en-US', {
      month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit',
    })
  } catch { return v }
}

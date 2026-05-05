'use client'

import { CheckCircle2, AlertCircle, Loader2, MinusCircle } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { WorkflowRunListItem } from '@/lib/api'


interface RunsListProps {
  runs:        WorkflowRunListItem[]
  selectedId:  number | null
  onSelect:    (runId: number) => void
}


export function RunsList({ runs, selectedId, onSelect }: RunsListProps) {
  return (
    <div className="rounded-xl bg-surface border border-border/8 overflow-hidden">
      <header className="px-5 py-3 border-b border-border/6 flex items-center gap-2">
        <h3 className="text-sm font-medium text-foreground">Recent Runs</h3>
        <span className="text-[11px] text-foreground-3">{runs.length}</span>
      </header>

      {runs.length === 0 ? (
        <p className="px-5 py-8 text-center text-sm text-foreground-3">
          No runs yet. Try one from the Lead page.
        </p>
      ) : (
        <ul className="divide-y divide-border/6">
          {runs.map((r) => {
            const active = r.run_id === selectedId
            return (
              <li key={r.run_id}>
                <button
                  onClick={() => onSelect(r.run_id)}
                  className={cn(
                    'w-full text-left px-5 py-3 flex items-start gap-3',
                    'transition-colors',
                    active
                      ? 'bg-surface-high'
                      : 'hover:bg-surface-high/50',
                  )}
                >
                  {/* Run id + status */}
                  <div className="shrink-0 flex flex-col items-start gap-1 w-[5rem]">
                    <span className="text-[11px] font-mono text-foreground-3">
                      #{r.run_id}
                    </span>
                    <StatusBadge status={r.status} />
                  </div>

                  {/* Domain + industry + email subject */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-baseline gap-2 flex-wrap">
                      <p className="text-[13px] font-medium text-foreground line-clamp-1">
                        {r.domain ?? r.input_url ?? '(unknown)'}
                      </p>
                      {r.industry && (
                        <span className="text-[10px] font-mono text-foreground-3">
                          {r.industry}
                        </span>
                      )}
                    </div>
                    {r.email_subject && (
                      <p className="mt-0.5 text-[11px] text-foreground-2 line-clamp-1">
                        {r.email_subject}
                      </p>
                    )}
                    <div className="mt-1 flex items-center gap-3 text-[10px] font-mono text-foreground-3">
                      {r.composite != null && (
                        <span className={cn(
                          r.qualified ? 'text-emerald-400' : 'text-amber-400',
                        )}>
                          {r.composite.toFixed(2)} {r.qualified ? '✓' : '✗'}
                        </span>
                      )}
                      {r.duration_ms != null && (
                        <span>{(r.duration_ms / 1000).toFixed(1)}s</span>
                      )}
                      {r.total_cost_usd != null && (
                        <span>${r.total_cost_usd.toFixed(4)}</span>
                      )}
                      {r.created_at && (
                        <span>{relativeTime(r.created_at)}</span>
                      )}
                    </div>
                  </div>
                </button>
              </li>
            )
          })}
        </ul>
      )}
    </div>
  )
}


function StatusBadge({ status }: { status: WorkflowRunListItem['status'] }) {
  const cls = 'inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[9px] font-mono uppercase tracking-[0.12em]'
  if (status === 'success') return <span className={cn(cls, 'text-emerald-400 bg-emerald-500/10')}><CheckCircle2 size={10} />ok</span>
  if (status === 'failed')  return <span className={cn(cls, 'text-rose-400    bg-rose-500/10'   )}><AlertCircle  size={10} />fail</span>
  if (status === 'running') return <span className={cn(cls, 'text-accent-blue bg-accent-blue/10')}><Loader2 size={10} className="animate-spin" />run</span>
  return                            <span className={cn(cls, 'text-foreground-3 bg-surface-high')}><MinusCircle size={10} />{status}</span>
}


function relativeTime(iso: string): string {
  const t = new Date(iso).getTime()
  const sec = Math.max(1, Math.round((Date.now() - t) / 1000))
  if (sec < 60)    return `${sec}s ago`
  if (sec < 3600)  return `${Math.round(sec / 60)}m ago`
  if (sec < 86400) return `${Math.round(sec / 3600)}h ago`
  return `${Math.round(sec / 86400)}d ago`
}

'use client'

import { CheckCircle2, AlertCircle, MinusCircle } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { TopLead } from '@/lib/api'


interface TopLeadsTableProps {
  rows: TopLead[]
}

export function TopLeadsTable({ rows }: TopLeadsTableProps) {
  return (
    <div className="rounded-xl bg-surface border border-border/8 overflow-hidden">
      <header className="px-5 py-3 border-b border-border/6 flex items-center gap-2">
        <h3 className="text-sm font-medium text-foreground">Top Leads &amp; Metrics</h3>
        <span className="text-[11px] text-foreground-3">{rows.length} most recent</span>
      </header>

      {rows.length === 0 ? (
        <p className="px-5 py-8 text-center text-sm text-foreground-3">
          No leads yet — try one from the Lead page.
        </p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-surface-high/40">
              <tr className="text-left text-[10px] font-mono text-foreground-3 tracking-[0.1em] uppercase">
                <th className="px-4 py-2.5 w-[3.5rem]">#</th>
                <th className="px-3 py-2.5">Domain</th>
                <th className="px-3 py-2.5">Industry</th>
                <th className="px-3 py-2.5 w-[5.5rem]">Composite</th>
                <th className="px-3 py-2.5 w-[6rem]">Status</th>
                <th className="px-3 py-2.5">Email subject</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((l) => (
                <tr key={l.lead_id} className="border-t border-border/6">
                  <td className="px-4 py-2.5 font-mono text-[11px] text-foreground-3">
                    #{l.lead_id}
                  </td>
                  <td className="px-3 py-2.5 text-[13px]">
                    <p className="text-foreground line-clamp-1 max-w-[14rem]">
                      {l.domain ?? l.input_url}
                    </p>
                  </td>
                  <td className="px-3 py-2.5 text-[12px] text-foreground-2">
                    {l.industry ?? '—'}
                  </td>
                  <td className="px-3 py-2.5 text-[12px] font-mono tabular-nums text-foreground-2">
                    {l.composite != null ? l.composite.toFixed(2) : '—'}
                  </td>
                  <td className="px-3 py-2.5">
                    <Status passed={l.qualified} runStatus={l.run_status} />
                  </td>
                  <td className="px-3 py-2.5 text-[12px] text-foreground-2">
                    <p className="line-clamp-1 max-w-[28rem]">
                      {l.email_subject ?? '—'}
                    </p>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}


function Status({
  passed, runStatus,
}: { passed: boolean | null; runStatus: string | null }) {
  if (runStatus === 'failed') {
    return <Pill kind="amber" icon={AlertCircle}>failed</Pill>
  }
  if (runStatus === 'running' || runStatus === 'queued') {
    return <Pill kind="muted" icon={MinusCircle}>{runStatus}</Pill>
  }
  if (passed === true)  return <Pill kind="emerald" icon={CheckCircle2}>qualified</Pill>
  if (passed === false) return <Pill kind="amber"   icon={AlertCircle}>unqualified</Pill>
  return <Pill kind="muted" icon={MinusCircle}>n/a</Pill>
}


function Pill({
  kind, icon: Icon, children,
}: {
  kind: 'emerald' | 'amber' | 'muted'
  icon: React.ComponentType<{ size?: number }>
  children: React.ReactNode
}) {
  return (
    <span className={cn(
      'inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-mono uppercase tracking-[0.12em]',
      kind === 'emerald' && 'text-emerald-400 bg-emerald-500/10',
      kind === 'amber'   && 'text-amber-400   bg-amber-500/10',
      kind === 'muted'   && 'text-foreground-3 bg-surface-high',
    )}>
      <Icon size={10} />
      {children}
    </span>
  )
}

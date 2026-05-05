'use client'

import { Fragment, type ReactNode, useState } from 'react'
import { Mail, Loader2, Copy, Check } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { StepMeta } from '@/lib/api'


interface EmailDraftCardProps {
  meta:    StepMeta | null
  pending: boolean
}


export function EmailDraftCard({ meta, pending }: EmailDraftCardProps) {
  const [copied, setCopied] = useState(false)
  const hasData = !!(meta && meta.subject && meta.body)

  const onCopy = async () => {
    if (!hasData) return
    try {
      await navigator.clipboard.writeText(`${meta!.subject}\n\n${meta!.body}`)
      setCopied(true)
      window.setTimeout(() => setCopied(false), 1500)
    } catch { /* clipboard might be blocked */ }
  }

  return (
    <div className="rounded-xl bg-surface border border-border/8 overflow-hidden">
      <header className="px-5 py-3 border-b border-border/6 flex items-center gap-2.5">
        <Mail size={15} className="text-accent-blue" />
        <h3 className="text-sm font-medium text-foreground">Outreach Email</h3>
        <div className="flex-1" />
        {meta?.tone && (
          <span className="text-[10px] font-mono text-foreground-3 tracking-[0.12em] uppercase">
            tone: {meta.tone}
          </span>
        )}
        {pending && !hasData && (
          <span className="text-[10px] font-mono text-foreground-3 tracking-[0.15em] uppercase inline-flex items-center gap-1.5">
            <Loader2 size={11} className="animate-spin" />
            drafting
          </span>
        )}
        {hasData && (
          <button
            onClick={onCopy}
            className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-mono text-foreground-3 hover:text-foreground hover:bg-surface-high transition-colors"
            title="Copy subject + body"
          >
            {copied
              ? <><Check size={10} className="text-emerald-400" /> copied</>
              : <><Copy size={10} /> copy</>}
          </button>
        )}
      </header>

      <div className="px-5 py-4">
        {!hasData && !pending && (
          <p className="text-[12px] text-foreground-3 text-center py-6">
            Email draft arrives after qualification completes.
          </p>
        )}

        {hasData && (
          <>
            {/* Subject */}
            <div className="pb-3 mb-3 border-b border-border/6">
              <p className="text-[10px] font-mono text-foreground-3 tracking-[0.12em] uppercase mb-1">
                Subject
              </p>
              <p className="text-[14px] font-medium text-foreground leading-snug">
                {meta!.subject}
              </p>
            </div>

            {/* Body with citation chips */}
            <div className="text-[13px] leading-[1.65] text-foreground-2 whitespace-pre-wrap text-pretty">
              {renderBodyWithCitations(meta!.body!, meta!.cited_findings ?? [])}
            </div>

            {/* Cited findings + unknown */}
            <div className="mt-4 pt-3 border-t border-border/6 flex items-start gap-3 flex-wrap text-[10px] font-mono">
              {meta!.cited_findings && meta!.cited_findings.length > 0 && (
                <div>
                  <span className="text-foreground-3 tracking-[0.12em] uppercase mr-1">
                    Cited:
                  </span>
                  {meta!.cited_findings.map((f) => (
                    <span
                      key={f}
                      className="ml-1 inline-block px-1.5 py-0.5 rounded bg-accent-warm/15 text-accent-warm"
                    >
                      {f}
                    </span>
                  ))}
                </div>
              )}
              {meta!.unknown_citations && meta!.unknown_citations.length > 0 && (
                <div>
                  <span className="text-amber-400 tracking-[0.12em] uppercase mr-1">
                    Unknown:
                  </span>
                  {meta!.unknown_citations.map((f) => (
                    <span
                      key={f}
                      className="ml-1 inline-block px-1.5 py-0.5 rounded bg-amber-500/15 text-amber-400"
                    >
                      {f}
                    </span>
                  ))}
                </div>
              )}
              {meta!.cost_usd != null && (
                <span className="ml-auto text-foreground-3">
                  ${meta!.cost_usd.toFixed(4)}
                </span>
              )}
            </div>
          </>
        )}
      </div>
    </div>
  )
}


/** Replace `[research.<field>]` markers with styled inline chips. */
function renderBodyWithCitations(body: string, cited: string[]): ReactNode {
  const re = /\[(research\.[a-z_][a-z0-9_]*)\]/gi
  const knownLower = new Set(cited.map((c) => c.toLowerCase()))
  const parts: ReactNode[] = []
  let last = 0
  let key = 0

  for (const m of body.matchAll(re)) {
    const idx = m.index ?? 0
    if (idx > last) parts.push(<Fragment key={key++}>{body.slice(last, idx)}</Fragment>)

    const marker = m[1]
    const isKnown = knownLower.has(marker.toLowerCase())
    parts.push(
      <span
        key={key++}
        className={cn(
          'inline-flex items-center align-baseline mx-0.5',
          'px-1.5 rounded text-[10px] font-mono',
          isKnown
            ? 'bg-accent-warm/15 text-accent-warm'
            : 'bg-amber-500/15 text-amber-400',
        )}
        title={marker}
      >
        {marker}
      </span>
    )
    last = idx + m[0].length
  }

  if (last < body.length) parts.push(<Fragment key={key++}>{body.slice(last)}</Fragment>)
  return parts
}

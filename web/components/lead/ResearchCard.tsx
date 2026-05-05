'use client'

import { FileSearch2, Loader2, Building2, Users, Newspaper, Cpu } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { StepMeta } from '@/lib/api'


interface ResearchCardProps {
  meta:    StepMeta | null     // step.metadata for the research step
  pending: boolean
}


export function ResearchCard({ meta, pending }: ResearchCardProps) {
  const hasData = !!(meta && (meta.industry || meta.headline || meta.summary))

  return (
    <div className="rounded-xl bg-surface border border-border/8 overflow-hidden">
      <header className="px-5 py-3 border-b border-border/6 flex items-center gap-2.5">
        <FileSearch2 size={15} className="text-accent-blue" />
        <h3 className="text-sm font-medium text-foreground">Research</h3>
        <div className="flex-1" />
        {pending && (
          <span className="text-[10px] font-mono text-foreground-3 tracking-[0.15em] uppercase inline-flex items-center gap-1.5">
            <Loader2 size={11} className="animate-spin" />
            extracting
          </span>
        )}
        {hasData && meta?.cost_usd != null && (
          <span className="text-[10px] font-mono text-foreground-3">
            ${meta.cost_usd.toFixed(4)}
          </span>
        )}
      </header>

      <div className="px-5 py-4 space-y-4">
        {!hasData && !pending && (
          <p className="text-[12px] text-foreground-3 text-center py-4">
            Research arrives after the first 4 steps complete.
          </p>
        )}

        {hasData && (
          <>
            {/* Headline + summary */}
            {meta?.headline && (
              <div>
                <p className="text-[15px] text-foreground leading-snug">
                  {meta.headline}
                </p>
                {meta.summary && (
                  <p className="mt-2 text-[13px] text-foreground-2 leading-relaxed">
                    {meta.summary}
                  </p>
                )}
              </div>
            )}

            {/* Badges */}
            <div className="flex flex-wrap gap-2">
              {meta?.industry && <Badge icon={Building2} label={meta.industry} />}
              {meta?.size     && <Badge icon={Users}     label={meta.size} />}
            </div>

            {/* Tech stack */}
            {meta?.tech_stack && meta.tech_stack.length > 0 && (
              <div>
                <SectionTitle icon={Cpu} label="Tech stack" />
                <div className="flex flex-wrap gap-1.5">
                  {meta.tech_stack.map((t) => (
                    <span key={t} className="px-2 py-0.5 rounded text-[11px] font-mono bg-surface-high text-foreground-2">
                      {t}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {/* Key people */}
            {meta?.key_people && meta.key_people.length > 0 && (
              <div>
                <SectionTitle icon={Users} label="Key people" />
                <ul className="space-y-1">
                  {meta.key_people.map((p, i) => (
                    <li key={i} className="text-[12px] text-foreground-2">
                      <span className="text-foreground font-medium">{p.name}</span>
                      {p.role && <span className="text-foreground-3"> — {p.role}</span>}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {/* Recent news */}
            {meta?.recent_news && meta.recent_news.length > 0 && (
              <div>
                <SectionTitle icon={Newspaper} label="Recent news" count={meta.recent_news.length} />
                <ul className="space-y-2">
                  {meta.recent_news.slice(0, 4).map((n, i) => (
                    <li key={i} className="text-[12px] leading-snug">
                      {n.url ? (
                        <a
                          href={n.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-foreground hover:text-accent-warm underline-offset-2 hover:underline"
                        >
                          {n.title}
                        </a>
                      ) : (
                        <span className="text-foreground">{n.title}</span>
                      )}
                      {n.summary && (
                        <p className="text-foreground-3 text-[11px] mt-0.5">
                          {n.summary}
                        </p>
                      )}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  )
}


function Badge({ icon: Icon, label }: { icon: React.ComponentType<{ size?: number; className?: string }>; label: string }) {
  return (
    <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-surface-high text-[12px] text-foreground-2">
      <Icon size={11} className="text-accent-blue" />
      {label}
    </span>
  )
}


function SectionTitle({
  icon: Icon, label, count,
}: { icon: React.ComponentType<{ size?: number; className?: string }>; label: string; count?: number }) {
  return (
    <div className="flex items-center gap-1.5 mb-1.5">
      <Icon size={11} className="text-foreground-3" />
      <p className={cn(
        'text-[10px] font-mono text-foreground-3 tracking-[0.12em] uppercase',
      )}>
        {label}
        {count != null && <span className="ml-1 normal-case tracking-normal">({count})</span>}
      </p>
    </div>
  )
}

'use client'

import type { ComponentType } from 'react'

interface KpiCardProps {
  label: string
  value: string
  hint?: string
  icon?: ComponentType<{ size?: number; className?: string }>
}

export function KpiCard({ label, value, hint, icon: Icon }: KpiCardProps) {
  return (
    <div className="p-5 rounded-xl bg-surface border border-border/8">
      <div className="flex items-start justify-between">
        <p className="text-xs font-medium text-foreground-2">{label}</p>
        {Icon && <Icon size={14} className="text-foreground-3" />}
      </div>
      <p className="mt-2 font-display text-3xl font-bold tabular-nums leading-none">
        {value}
      </p>
      {hint && (
        <p className="mt-2 text-[10px] font-mono text-foreground-3 tracking-[0.1em] uppercase">
          {hint}
        </p>
      )}
    </div>
  )
}

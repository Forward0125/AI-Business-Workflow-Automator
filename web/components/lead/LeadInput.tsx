'use client'

import { useState } from 'react'
import { Sparkles, Globe, Loader2 } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { Tone } from '@/lib/api'

const TONE_OPTIONS: { value: Tone; label: string; hint: string }[] = [
  { value: 'executive', label: 'Executive', hint: 'Direct, time-respecting, exec-focused' },
  { value: 'technical', label: 'Technical', hint: 'Engineer-friendly, lean on tech_stack' },
  { value: 'casual',    label: 'Casual',    hint: 'Warm, human, business-appropriate' },
]

const EXAMPLES = [
  { label: 'stripe.com',    url: 'https://stripe.com' },
  { label: 'anthropic.com', url: 'https://anthropic.com' },
  { label: 'vercel.com',    url: 'https://vercel.com' },
]


export interface LeadInputProps {
  onSubmit:    (url: string, tone: Tone) => void
  disabled:    boolean
  initialUrl?: string
  initialTone?: Tone
}


export function LeadInput({
  onSubmit,
  disabled,
  initialUrl  = '',
  initialTone = 'executive',
}: LeadInputProps) {
  const [url,  setUrl]  = useState(initialUrl)
  const [tone, setTone] = useState<Tone>(initialTone)

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault()
        if (!url.trim() || disabled) return
        onSubmit(url.trim(), tone)
      }}
      className="space-y-3"
    >
      {/* URL input */}
      <div className="relative">
        <Globe
          size={18}
          className="absolute left-4 top-1/2 -translate-y-1/2 text-foreground-3 pointer-events-none"
        />
        <input
          type="text"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          disabled={disabled}
          placeholder="Paste a company URL — https://stripe.com"
          className={cn(
            'w-full pl-11 pr-32 py-3.5 rounded-xl text-[15px]',
            'bg-surface border border-border/10',
            'text-foreground placeholder:text-foreground-3',
            'focus:outline-none focus:border-accent-warm/40',
            'disabled:opacity-60 disabled:cursor-not-allowed',
            'transition-colors',
          )}
        />
        <button
          type="submit"
          disabled={disabled || !url.trim()}
          className={cn(
            'absolute right-2 top-1/2 -translate-y-1/2',
            'inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg',
            'text-[13px] font-medium',
            'bg-accent-warm text-white hover:bg-accent-violet',
            'disabled:bg-surface-high disabled:text-foreground-3',
            'transition-colors',
          )}
        >
          {disabled ? (
            <>
              <Loader2 size={13} className="animate-spin" />
              Running
            </>
          ) : (
            <>
              <Sparkles size={13} />
              Run
            </>
          )}
        </button>
      </div>

      {/* Tone chips */}
      <div className="flex items-center flex-wrap gap-2" role="radiogroup" aria-label="Tone">
        <span className="text-[10px] font-mono text-foreground-3 tracking-[0.15em] uppercase mr-1">
          Tone
        </span>
        {TONE_OPTIONS.map(({ value, label, hint }) => (
          <button
            key={value}
            type="button"
            role="radio"
            aria-checked={tone === value}
            title={hint}
            onClick={() => setTone(value)}
            disabled={disabled}
            className={cn(
              'px-2.5 py-1 rounded-md text-[11px] font-medium border transition-colors duration-150 disabled:opacity-50',
              tone === value
                ? 'bg-accent-warm/15 border-accent-warm/30 text-accent-warm'
                : 'bg-surface border-border/10 text-foreground-2 hover:text-foreground hover:bg-surface-high',
            )}
          >
            {label}
          </button>
        ))}
      </div>

      {/* Quick examples */}
      <div className="flex items-center flex-wrap gap-2">
        <span className="text-[10px] font-mono text-foreground-3 tracking-[0.15em] uppercase mr-1">
          Try
        </span>
        {EXAMPLES.map(({ label, url: u }) => (
          <button
            key={u}
            type="button"
            onClick={() => setUrl(u)}
            disabled={disabled}
            className={cn(
              'px-2.5 py-1 rounded-md text-[11px] font-medium border',
              'bg-surface border-border/10 text-foreground-2',
              'hover:text-foreground hover:bg-surface-high transition-colors',
              'disabled:opacity-50',
            )}
          >
            {label}
          </button>
        ))}
      </div>
    </form>
  )
}

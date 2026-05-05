import { Container } from '@/components/ui/Container'

export const metadata = { title: 'Workflows' }

export default function WorkflowsPage() {
  return (
    <Container size="full" className="py-8 md:py-12">
      <p className="text-[11px] font-mono text-foreground-3 tracking-[0.15em] uppercase mb-3">
        Workflows
      </p>
      <h1 className="font-display text-4xl md:text-5xl font-bold tracking-tight">
        Lead-to-conversion as a DAG.
      </h1>
      <p className="mt-3 text-foreground-2 max-w-2xl">
        Visual graph of every workflow run. Pick a recent run to replay
        its steps, or kick off a new one. UI ships in step 11; SSE-driven
        animation reuses the InsightFinder pattern.
      </p>

      <div className="mt-10 p-8 rounded-xl bg-surface border border-border/8 max-w-2xl">
        <p className="text-sm text-foreground-3 font-mono">
          $ alembic upgrade head{'\n'}
          ✓ schema applied{'\n'}
          ⏳ workflow engine pending (steps 6–10)
        </p>
      </div>
    </Container>
  )
}

'use client'

import { memo, useMemo } from 'react'
import {
  Background,
  ReactFlow,
  type Edge,
  type Node,
  type NodeProps,
} from '@xyflow/react'
import {
  Globe, Search, FileSearch2, ShieldCheck, Mail,
  Briefcase, Calendar, Send, CheckCircle2, AlertCircle, Loader2, Circle,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import type { StepInfo, StepName, StepStatus } from '@/lib/api'

import '@xyflow/react/dist/style.css'


/* ─── Step definitions ──────────────────────────────────────── */

interface StepDef {
  name:  StepName
  label: string
  icon:  React.ComponentType<{ size?: number; className?: string }>
}

const STEPS: StepDef[] = [
  { name: 'fetch',       label: 'Fetch',       icon: Globe        },
  { name: 'web_search',  label: 'Web Search',  icon: Search       },
  { name: 'research',    label: 'Research',    icon: FileSearch2  },
  { name: 'qualify',     label: 'Qualify',     icon: ShieldCheck  },
  { name: 'personalize', label: 'Personalize', icon: Mail         },
  { name: 'crm',         label: 'CRM',         icon: Briefcase    },
  { name: 'calendar',    label: 'Calendar',    icon: Calendar     },
  { name: 'email',       label: 'Email',       icon: Send         },
]


/* ─── Custom node ───────────────────────────────────────────── */

interface DAGNodeData extends Record<string, unknown> {
  step:   StepDef
  status: StepStatus
  meta:   StepInfo['metadata']
}

const DAGNode = memo(function DAGNode({ data }: NodeProps<Node<DAGNodeData>>) {
  const { step, status, meta } = data
  const Icon = step.icon

  const subtitle = subtitleFor(step.name, status, meta)

  return (
    <div
      className={cn(
        'w-[140px] px-3 py-2.5 rounded-lg border text-left',
        'transition-colors duration-200',
        status === 'queued'  && 'bg-surface       border-border/8     text-foreground-3',
        status === 'running' && 'bg-accent-blue/10 border-accent-blue/30 text-foreground',
        status === 'success' && 'bg-emerald-500/10 border-emerald-500/30 text-foreground',
        status === 'failed'  && 'bg-rose-500/10    border-rose-500/30   text-foreground',
      )}
    >
      <div className="flex items-center justify-between mb-1">
        <Icon size={14} />
        <StatusBadge status={status} />
      </div>
      <p className="text-[12px] font-medium leading-tight">{step.label}</p>
      {subtitle && (
        <p className="mt-1 text-[10px] font-mono text-foreground-3 truncate">
          {subtitle}
        </p>
      )}
    </div>
  )
})


function StatusBadge({ status }: { status: StepStatus }) {
  if (status === 'running') return <Loader2 size={11} className="text-accent-blue animate-spin" />
  if (status === 'success') return <CheckCircle2 size={11} className="text-emerald-400" />
  if (status === 'failed')  return <AlertCircle size={11} className="text-rose-400" />
  return <Circle size={11} className="text-foreground-3/40" />
}


function subtitleFor(name: StepName, status: StepStatus, meta: StepInfo['metadata']): string | null {
  if (!meta || status !== 'success') return null
  switch (name) {
    case 'fetch':       return meta.fetched_bytes ? `${Math.round(meta.fetched_bytes / 1024)} KB` : null
    case 'web_search':  return meta.hits != null ? `${meta.hits} hits` : null
    case 'research':    return meta.industry ? `industry: ${meta.industry}` : null
    case 'qualify':     return meta.composite != null ? `${meta.composite.toFixed(2)} ${meta.qualified ? '✓' : '✗'}` : null
    case 'personalize': return meta.tone ? `tone: ${meta.tone}` : null
    case 'crm':
    case 'calendar':
    case 'email':       return meta.duration_ms ? `${meta.duration_ms}ms` : null
    default:            return null
  }
}


const NODE_TYPES = { dag: DAGNode } as const


/* ─── DAG component ─────────────────────────────────────────── */

type StepMap = Partial<Record<StepName, StepInfo>>


interface WorkflowDAGProps {
  steps: StepMap
}


export function WorkflowDAG({ steps }: WorkflowDAGProps) {
  const { nodes, edges } = useMemo(() => {
    // 2 rows of 4 nodes each. Tighter than 8 in a single row.
    const ROW1 = STEPS.slice(0, 4)
    const ROW2 = STEPS.slice(4)
    const NODE_W = 140
    const GAP_X  = 60
    const ROW_Y  = [16, 132]

    const nodes: Node<DAGNodeData>[] = []
    const edges: Edge[] = []

    const addRow = (row: StepDef[], y: number) => {
      row.forEach((step, i) => {
        const x = i * (NODE_W + GAP_X)
        const info = steps[step.name]
        nodes.push({
          id:       step.name,
          type:     'dag',
          position: { x, y },
          draggable: false,
          selectable: false,
          data: {
            step,
            status: (info?.status ?? 'queued') as StepStatus,
            meta:   info?.metadata ?? null,
          },
        })
      })
    }

    addRow(ROW1, ROW_Y[0])
    addRow(ROW2, ROW_Y[1])

    // Linear edges across all 8 in DAG order.
    for (let i = 0; i < STEPS.length - 1; i++) {
      const from = STEPS[i].name
      const to   = STEPS[i + 1].name
      const fromInfo = steps[from]
      const toInfo   = steps[to]
      const isActive = fromInfo?.status === 'success'
      edges.push({
        id:     `${from}-${to}`,
        source: from,
        target: to,
        animated: toInfo?.status === 'running',
        style: {
          stroke: isActive ? 'rgb(163 106 254 / 0.4)' : 'rgb(255 255 255 / 0.08)',
          strokeWidth: 1.5,
        },
      })
    }

    return { nodes, edges }
  }, [steps])

  return (
    <div className="rounded-xl bg-surface border border-border/8 overflow-hidden">
      <header className="px-5 py-3 border-b border-border/6 flex items-center gap-2">
        <h3 className="text-sm font-medium text-foreground">Workflow</h3>
        <p className="text-[11px] text-foreground-3">8 steps · live</p>
      </header>
      <div className="h-[260px]">
        <ReactFlow
          nodes={nodes}
          edges={edges}
          nodeTypes={NODE_TYPES}
          fitView
          fitViewOptions={{ padding: 0.15 }}
          nodesDraggable={false}
          nodesConnectable={false}
          elementsSelectable={false}
          panOnDrag={false}
          panOnScroll={false}
          zoomOnScroll={false}
          zoomOnPinch={false}
          zoomOnDoubleClick={false}
          proOptions={{ hideAttribution: true }}
        >
          <Background gap={16} color="rgb(255 255 255 / 0.03)" />
        </ReactFlow>
      </div>
    </div>
  )
}

import { useEffect, useState } from 'react'
import { useAgent } from '@copilotkit/react-core/v2'
import type { CustomEvent as AguiCustomEvent } from '@ag-ui/client'

// design.md S8 (US-06, D8, D9, D13): renders CanvasBlocks emitted by the
// backend as CUSTOM events (name="CANVAS_BLOCK"). Read-only (D9) -- no
// save/edit affordance. Accumulates across the whole session so earlier
// turns' blocks stay visible, tagged by `source` (D13).

interface CanvasBlock {
  language: string
  content: string
  source: 'response_text' | 'tool_output'
}

export default function CanvasPane({ hidden }: { hidden: boolean }) {
  const { agent } = useAgent({ agentId: 'default' })
  const [blocks, setBlocks] = useState<CanvasBlock[]>([])

  useEffect(() => {
    const subscription = agent.subscribe({
      onCustomEvent: ({ event }: { event: AguiCustomEvent }) => {
        if (event.name === 'CANVAS_BLOCK') {
          setBlocks((prev) => [...prev, event.value as CanvasBlock])
        }
      },
    })
    return () => subscription.unsubscribe()
  }, [agent])

  if (hidden) return null

  return (
    <section className="canvas-pane" aria-label="canvas">
      {blocks.length === 0 && (
        <div className="canvas-empty">No canvas content yet.</div>
      )}
      {blocks.map((block, i) => (
        <div className="canvas-block" key={i}>
          <div className="canvas-block-header">
            {block.language} &middot; {block.source}
          </div>
          <pre>{block.content}</pre>
        </div>
      ))}
    </section>
  )
}

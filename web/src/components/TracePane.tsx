import { useEffect, useReducer, useRef, useState } from 'react'

// design.md S6 (US-04, D12): connects DIRECTLY to M2's existing WsBridgeSink
// -- no backend proxying. Fetches {ws_url, ws_token} once on mount (passing
// the shared threadId, D21, so the session -- and its observability_config
// -- exists even before the first chat turn), then opens its own WebSocket
// and renders span_start/span_end/gap_marker records into a span_id/
// parent_span_id tree (AC-04.2), flagging gaps (AC-04.3).

interface SpanRecord {
  record_type: 'span_start' | 'span_end' | 'gap_marker'
  span_id?: string | null
  parent_span_id?: string | null
  phase?: string | null
  span_name?: string | null
  status?: string | null
  duration_ms?: number | null
  drop_count?: number
}

interface SpanNode extends Partial<SpanRecord> {
  children: SpanNode[]
}

function TraceTree({ node, isRoot }: { node: SpanNode; isRoot: boolean }) {
  return (
    <div className={`trace-node ${isRoot ? 'root' : ''}`}>
      <div className={node.status === 'ERROR' ? 'trace-status-ERROR' : undefined}>
        <span className="trace-phase">[{node.phase ?? '?'}]</span> {node.span_name}
        {node.duration_ms != null ? ` (${node.duration_ms.toFixed(1)}ms)` : ''}
      </div>
      {node.children.map((child) => (
        <TraceTree key={child.span_id} node={child} isRoot={false} />
      ))}
    </div>
  )
}

export default function TracePane({ threadId }: { threadId: string }) {
  const [gaps, setGaps] = useState<SpanRecord[]>([])
  const [status, setStatus] = useState<'connecting' | 'open' | 'unavailable'>(
    'connecting',
  )
  const nodesRef = useRef<Map<string, SpanNode>>(new Map())
  const rootIdsRef = useRef<string[]>([])
  const [, forceRender] = useReducer((c: number) => c + 1, 0)

  useEffect(() => {
    let ws: WebSocket | null = null
    let cancelled = false

    fetch(`/api/trace-endpoint?threadId=${encodeURIComponent(threadId)}`)
      .then((res) => {
        if (!res.ok) throw new Error(`trace-endpoint ${res.status}`)
        return res.json()
      })
      .then(({ ws_url, ws_token }: { ws_url: string; ws_token: string }) => {
        if (cancelled) return
        ws = new WebSocket(`${ws_url}?token=${encodeURIComponent(ws_token)}`)
        ws.onopen = () => setStatus('open')
        ws.onerror = () => setStatus('unavailable')
        ws.onclose = () => setStatus('unavailable')
        ws.onmessage = (evt) => {
          const record: SpanRecord = JSON.parse(evt.data)
          if (record.record_type === 'gap_marker') {
            setGaps((prev) => [...prev, record])
            return
          }
          const spanId = record.span_id
          if (!spanId) return
          const nodes = nodesRef.current
          let node = nodes.get(spanId)
          if (!node) {
            node = { children: [] }
            nodes.set(spanId, node)
            const parent = record.parent_span_id
              ? nodes.get(record.parent_span_id)
              : undefined
            if (parent) {
              parent.children.push(node)
            } else {
              // Root, or parent not seen yet (out-of-order arrival) --
              // rendered at top level either way; not reparented later.
              rootIdsRef.current.push(spanId)
            }
          }
          Object.assign(node, record)
          forceRender()
        }
      })
      .catch(() => {
        if (!cancelled) setStatus('unavailable')
      })

    return () => {
      cancelled = true
      ws?.close()
    }
  }, [threadId])

  if (status === 'unavailable') {
    return (
      <aside className="trace-pane" aria-label="trace">
        <div className="trace-empty">trace unavailable</div>
      </aside>
    )
  }

  const roots = rootIdsRef.current
    .map((id) => nodesRef.current.get(id))
    .filter((n): n is SpanNode => n != null)

  return (
    <aside className="trace-pane" aria-label="trace">
      {gaps.map((g, i) => (
        <div className="trace-gap" key={i}>
          gap: {g.drop_count} record(s) dropped
        </div>
      ))}
      {roots.length === 0 && <div className="trace-empty">no spans yet</div>}
      {roots.map((node) => (
        <TraceTree key={node.span_id} node={node} isRoot />
      ))}
    </aside>
  )
}

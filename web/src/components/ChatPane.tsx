import { useEffect, useRef, useState } from 'react'
import { useAgent } from '@copilotkit/react-core/v2'
import type { Message } from '@ag-ui/client'
import ApprovalPrompt from './ApprovalPrompt'

// design.md S3/S4 replacement (US-01, US-02): first-party chat surface,
// replacing CopilotKit's stock <CopilotChat> (dryrun-code-1 was clean on
// the old component; this supersedes it per the 009 preview review).
// Still driven entirely by the same HttpAgent/AG-UI event stream
// ApprovalPrompt.tsx/CanvasPane.tsx already subscribe to -- this is a
// rendering change, not a protocol change. agent.messages/onMessagesChanged
// already reflects streamed TEXT_MESSAGE_CONTENT deltas as they arrive
// (the framework applies them before notifying subscribers), so no manual
// buffer-tracking is needed for the streaming text itself.

const PRAO_PHASES = new Set(['perceive', 'reason', 'act', 'observe'])

interface TracePhaseRecord {
  record_type: 'span_start' | 'span_end' | 'gap_marker'
  phase?: string | null
}

function contentText(message: Message): string {
  return typeof message.content === 'string' ? message.content : ''
}

export default function ChatPane({ threadId }: { threadId: string }) {
  const { agent } = useAgent({ agentId: 'default' })
  const [messages, setMessages] = useState<Message[]>(() => [...agent.messages])
  const [running, setRunning] = useState(false)
  const [phase, setPhase] = useState<string | null>(null)
  const [input, setInput] = useState('')
  const scrollRef = useRef<HTMLDivElement>(null)
  const fieldRef = useRef<HTMLTextAreaElement>(null)

  useEffect(() => {
    const subscription = agent.subscribe({
      onMessagesChanged: ({ messages }) => setMessages([...messages]),
      onRunStartedEvent: () => setRunning(true),
      onRunFinishedEvent: () => {
        setRunning(false)
        setPhase(null)
      },
      onRunErrorEvent: () => {
        setRunning(false)
        setPhase(null)
      },
    })
    return () => subscription.unsubscribe()
  }, [agent])

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight })
  }, [messages, phase])

  // Real PRAO-phase indicator (not a simulated timer) -- reuses M2's
  // existing WS trace bridge, the same one TracePane.tsx connects to
  // (design.md D12, S6). WsBridgeSink broadcasts to every connected
  // client independently, so this and TracePane can both be open at
  // once. Opened fresh per turn -- only useful while one is in flight.
  useEffect(() => {
    if (!running) return
    let cancelled = false
    let ws: WebSocket | null = null

    fetch(`/api/trace-endpoint?threadId=${encodeURIComponent(threadId)}`)
      .then((res) => (res.ok ? res.json() : null))
      .then((cfg: { ws_url: string; ws_token: string } | null) => {
        if (cancelled || !cfg) return
        ws = new WebSocket(`${cfg.ws_url}?token=${encodeURIComponent(cfg.ws_token)}`)
        ws.onmessage = (evt) => {
          const record: TracePhaseRecord = JSON.parse(evt.data)
          if (
            record.record_type === 'span_start' &&
            record.phase &&
            PRAO_PHASES.has(record.phase)
          ) {
            setPhase(record.phase)
          }
        }
      })
      .catch(() => {
        // Trace bridge unavailable -- the phase tag just never appears;
        // the live-dot alone still communicates "in progress".
      })

    return () => {
      cancelled = true
      ws?.close()
    }
  }, [running, threadId])

  function autoGrow() {
    const el = fieldRef.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = `${el.scrollHeight}px`
  }

  async function send() {
    const text = input.trim()
    if (!text || running) return
    agent.addMessage({ id: crypto.randomUUID(), role: 'user', content: text })
    setMessages([...agent.messages])
    setInput('')
    requestAnimationFrame(autoGrow)
    try {
      await agent.runAgent()
    } catch {
      // onRunErrorEvent already resets running/phase; nothing else to do.
    }
  }

  const visible = messages.filter((m) => m.role === 'user' || m.role === 'assistant')
  const last = visible[visible.length - 1]
  const streamingReply = running && last?.role === 'assistant'
  const waitingForFirstToken = running && !streamingReply

  return (
    <section className="chat-pane">
      <ApprovalPrompt />
      <div className="msg-scroll" ref={scrollRef}>
        <div className="msg-list">
          {visible.map((m, i) => {
            const isStreaming = streamingReply && i === visible.length - 1
            return (
              <div className={`msg-row ${m.role}`} key={m.id}>
                <div className="msg-meta">
                  {isStreaming && <span className="live-dot" />}
                  <span className="who">{m.role === 'user' ? 'you' : 'axiom'}</span>
                  {isStreaming && phase && <span className="phase">[{phase}]</span>}
                </div>
                <div className="content">
                  {contentText(m)}
                  {isStreaming && <span className="cursor">▍</span>}
                </div>
              </div>
            )
          })}
          {waitingForFirstToken && (
            <div className="msg-row assistant">
              <div className="msg-meta">
                <span className="live-dot" />
                <span className="who">axiom</span>
                {phase && <span className="phase">[{phase}]</span>}
              </div>
            </div>
          )}
        </div>
      </div>

      <div className="composer">
        <div className="composer-inner">
          <div className="composer-row">
            <textarea
              ref={fieldRef}
              className="composer-field"
              rows={1}
              placeholder="Message axiom…"
              value={input}
              disabled={running}
              onChange={(e) => {
                setInput(e.target.value)
                autoGrow()
              }}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault()
                  send()
                }
              }}
            />
            <button
              type="button"
              className="send-btn"
              onClick={send}
              disabled={running || !input.trim()}
            >
              Send
            </button>
          </div>
          <div className="composer-hint">
            <span>Enter to send &middot; Shift+Enter for newline</span>
            <span className="status">
              <span className="status-dot" />
              connected
            </span>
          </div>
        </div>
      </div>
    </section>
  )
}

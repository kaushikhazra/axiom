import { useMemo, useRef, useState } from 'react'
import { CopilotKit } from '@copilotkit/react-core'
import { CopilotChat } from '@copilotkit/react-ui'
import { HttpAgent } from '@ag-ui/client'
import '@copilotkit/react-ui/styles.css'
import './theme.css'
import ApprovalPrompt from './components/ApprovalPrompt'
import TracePane from './components/TracePane'
import CanvasPane from './components/CanvasPane'
import ProviderSelector from './components/ProviderSelector'

// design.md D18: direct-agent wiring via @ag-ui/client's HttpAgent, passed
// as selfManagedAgents. <CopilotKit> (not the /v2 CopilotKitProvider
// directly) -- confirmed via Playwright browser verification that
// CopilotChat's useCopilotContext() requires the legacy context <CopilotKit>
// sets up around CopilotKitProvider; CopilotKitProvider alone left
// CopilotChat throwing "wrap your app in a <CopilotKit>" at runtime, a
// failure invisible to tsc (compatible prop types) and to curl (backend-only).
// selfManagedAgents is still a valid prop -- CopilotKitProps extends
// CopilotKitProviderProps. Registered under "default" (CopilotKit's own
// DEFAULT_AGENT_ID) so CopilotChat/useAgent resolve it with no extra
// agentId wiring.

function App() {
  const threadId = useRef(crypto.randomUUID()).current
  const httpAgent = useMemo(
    () => new HttpAgent({ url: '/api/agent/run', threadId }),
    [threadId],
  )
  const [canvasOpen, setCanvasOpen] = useState(true)
  const [traceOpen, setTraceOpen] = useState(false)

  return (
    <CopilotKit
      selfManagedAgents={{ default: httpAgent }}
      enableInspector={false}
      showDevConsole={false}
    >
      <div className="app-shell">
        <header className="chrome-bar">
          <span className="chrome-title">axiom</span>
          <ProviderSelector threadId={threadId} />
          <button
            type="button"
            className="chrome-toggle"
            aria-pressed={canvasOpen}
            onClick={() => setCanvasOpen((v) => !v)}
          >
            canvas
          </button>
          <button
            type="button"
            className="chrome-toggle"
            aria-pressed={traceOpen}
            onClick={() => setTraceOpen((v) => !v)}
          >
            trace
          </button>
        </header>
        <div className="app-body">
          <section className="chat-pane">
            <ApprovalPrompt />
            <CopilotChat
              className="axiom-chat"
              labels={{ title: 'axiom', initial: 'Ready.' }}
            />
          </section>
          {/* CanvasPane stays mounted across toggles -- unmounting would
              discard its accumulated blocks (it has no external state to
              restore from on remount), unlike TracePane below, which
              legitimately closes its WebSocket when hidden. */}
          <CanvasPane hidden={!canvasOpen} />
          {traceOpen && <TracePane threadId={threadId} />}
        </div>
      </div>
    </CopilotKit>
  )
}

export default App

import { useMemo, useRef, useState } from 'react'
import { CopilotKit } from '@copilotkit/react-core'
import { HttpAgent } from '@ag-ui/client'
import './theme.css'
import ChatPane from './components/ChatPane'
import TracePane from './components/TracePane'
import CanvasPane from './components/CanvasPane'
import ProviderSelector from './components/ProviderSelector'

// design.md D18: direct-agent wiring via @ag-ui/client's HttpAgent, passed
// as selfManagedAgents, registered under "default" (CopilotKit's own
// DEFAULT_AGENT_ID) so every component's useAgent({agentId: 'default'})
// resolves it with no extra wiring. <CopilotKit> (main entry, not the /v2
// CopilotKitProvider directly) is still used even though ChatPane replaced
// the stock <CopilotChat> that originally required its legacy context --
// selfManagedAgents is still a valid prop (CopilotKitProps extends
// CopilotKitProviderProps), and switching to the leaner provider isn't
// worth it for the enableInspector/showDevConsole props already tuned here.

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
          <ChatPane threadId={threadId} />
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

import { useMemo, useRef } from 'react'
import { CopilotKit } from '@copilotkit/react-core'
import { HttpAgent } from '@ag-ui/client'
import './theme.css'
import ChatPane from './components/ChatPane'

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
  return (
    <CopilotKit
      selfManagedAgents={{ default: httpAgent }}
      enableInspector={false}
      showDevConsole={false}
    >
      <div className="app-shell">
        {/* Canvas and trace panes removed (#17); provider dropdown removed
            (#19) -- provider is the Router's policy decision now. Chat is the
            whole surface. ChatPane still talks to the M2 trace bridge for its
            in-chat PRAO phase tag, which is why /api/trace-endpoint and
            WsBridgeSink deliberately survive. */}
        <header className="chrome-bar">
          <span className="chrome-title">axiom</span>
        </header>
        <div className="app-body">
          <ChatPane threadId={threadId} />
        </div>
      </div>
    </CopilotKit>
  )
}

export default App

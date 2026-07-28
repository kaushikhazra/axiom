import { useEffect, useState } from 'react'
import { useAgent } from '@copilotkit/react-core/v2'
import type { CustomEvent as AguiCustomEvent } from '@ag-ui/client'

// design.md S5 (US-03, D5, D6, D14): the backend emits tool-approval
// requests as an AG-UI CUSTOM event (name="TOOL_APPROVAL_REQUEST"), not a
// CopilotKit frontend-tool call -- subscribing directly to the agent's raw
// event stream (AgentSubscriber.onCustomEvent) is simpler and more explicit
// than routing it through CopilotKit's tool-call rendering machinery, which
// is designed for LLM-invoked tools rather than out-of-band HITL prompts.

interface PendingApproval {
  approval_id: string
  tool_name: string
  arguments: Record<string, unknown>
}

export default function ApprovalPrompt() {
  const { agent } = useAgent({ agentId: 'default' })
  const [pending, setPending] = useState<PendingApproval | null>(null)
  const [resolving, setResolving] = useState(false)

  useEffect(() => {
    const subscription = agent.subscribe({
      onCustomEvent: ({ event }: { event: AguiCustomEvent }) => {
        if (event.name === 'TOOL_APPROVAL_REQUEST') {
          setPending(event.value as PendingApproval)
        }
      },
    })
    return () => subscription.unsubscribe()
  }, [agent])

  if (!pending) return null

  const decide = async (approved: boolean) => {
    setResolving(true)
    try {
      await fetch(`/api/approval/${pending.approval_id}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ approved }),
      })
    } finally {
      setPending(null)
      setResolving(false)
    }
  }

  return (
    <div className="approval-prompt" role="alert">
      <strong>Tool approval requested: {pending.tool_name}</strong>
      <pre>{JSON.stringify(pending.arguments, null, 2)}</pre>
      <div className="approval-actions">
        <button
          className="approve"
          disabled={resolving}
          onClick={() => decide(true)}
        >
          Approve
        </button>
        <button className="deny" disabled={resolving} onClick={() => decide(false)}>
          Deny
        </button>
      </div>
    </div>
  )
}

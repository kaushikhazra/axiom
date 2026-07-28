import { useState } from 'react'

// design.md S7 (US-05, D4, D17): local state is the source of truth for
// what's displayed (D17) -- not a trace-derived AG-UI state event. The
// backend response confirms the change took effect; a failing request
// surfaces as an error instead of a silent revert.

type ProviderValue = 'claude' | 'local' | 'committee' | ''

export default function ProviderSelector({ threadId }: { threadId: string }) {
  const [provider, setProvider] = useState<ProviderValue>('')
  const [error, setError] = useState<string | null>(null)

  const onChange = async (value: ProviderValue) => {
    const previous = provider
    setProvider(value)
    setError(null)
    try {
      const resp = await fetch('/api/provider', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ threadId, provider: value || null }),
      })
      if (!resp.ok) throw new Error(`provider switch failed (${resp.status})`)
    } catch (err) {
      setProvider(previous)
      setError(err instanceof Error ? err.message : 'provider switch failed')
    }
  }

  return (
    <label>
      <select
        className="provider-select"
        value={provider}
        onChange={(e) => onChange(e.target.value as ProviderValue)}
        title={error ?? undefined}
      >
        <option value="">Auto (Router default)</option>
        <option value="claude">claude</option>
        <option value="local">local</option>
        <option value="committee">committee</option>
      </select>
    </label>
  )
}

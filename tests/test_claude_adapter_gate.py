"""
Unit tests for ClaudeAdapter._gate_hook (design.md §9, M4 Guardrails GATE).

No existing test constructs ClaudeAdapter or exercises the gate hook directly
(test_claude_adapter_spans.py only imports module-level span helper functions).
Covers: SAFE tools skip the approval seam, DESTRUCTIVE tools are gated,
approval/denial decisions map to the correct hook return shape, and an
approval_fn raising fails closed (dryrun-code-1 finding B2, KIND-B half).
"""

from __future__ import annotations

from unittest.mock import patch

import anyio

from axiom.providers.claude_adapter import ClaudeAdapter
from axiom.tools.guardrails import GuardrailsGate


def _make_adapter(gate: GuardrailsGate) -> ClaudeAdapter:
    return ClaudeAdapter(persona="test-persona", allowed_tools=["WebSearch"], gate=gate)


def _run_hook(adapter: ClaudeAdapter, tool_name: str, tool_input: dict) -> dict:
    input_data = {"tool_name": tool_name, "tool_input": tool_input}
    return anyio.run(adapter._gate_hook, input_data, "toolu_test", None)


class TestSafeTools:
    def test_web_search_returns_empty_dict_no_prompt(self) -> None:
        calls: list = []

        def _tracking_fn(name: str, args: dict) -> bool:
            calls.append(name)
            return True

        adapter = _make_adapter(GuardrailsGate(approval_fn=_tracking_fn))
        result = _run_hook(adapter, "WebSearch", {"query": "axiom"})
        assert result == {}
        assert calls == []  # approval seam never invoked for SAFE tools


class TestDestructiveTools:
    def test_bash_approved_returns_empty_dict(self) -> None:
        adapter = _make_adapter(GuardrailsGate(approval_fn=lambda n, a: True))
        result = _run_hook(adapter, "Bash", {"command": "echo hi"})
        assert result == {}

    def test_bash_denied_returns_deny_payload(self) -> None:
        adapter = _make_adapter(GuardrailsGate(approval_fn=lambda n, a: False))
        result = _run_hook(adapter, "Bash", {"command": "rm -rf /"})
        assert result["hookSpecificOutput"]["hookEventName"] == "PreToolUse"
        assert result["hookSpecificOutput"]["permissionDecision"] == "deny"
        assert (
            result["hookSpecificOutput"]["permissionDecisionReason"] == "denied by user"
        )

    def test_write_and_edit_are_also_gated(self) -> None:
        adapter = _make_adapter(GuardrailsGate(approval_fn=lambda n, a: False))
        for tool_name in ("Write", "Edit"):
            result = _run_hook(adapter, tool_name, {})
            assert result["hookSpecificOutput"]["permissionDecision"] == "deny"

    def test_auto_approve_skips_prompt(self) -> None:
        calls: list = []

        def _should_never_be_called(name: str, args: dict) -> bool:
            calls.append(name)
            return False

        adapter = _make_adapter(
            GuardrailsGate(auto_approve=True, approval_fn=_should_never_be_called)
        )
        result = _run_hook(adapter, "Bash", {"command": "echo hi"})
        assert result == {}
        assert calls == []


class TestApprovalFnRaises:
    """dryrun-code-1 finding B2 (KIND-B half): the approval step failing must
    fail closed (deny), not propagate out of the hook uncaught."""

    def test_raising_approval_fn_denies_not_raises(self) -> None:
        def _raises(name: str, args: dict) -> bool:
            raise ValueError("I/O operation on closed file (simulated)")

        adapter = _make_adapter(GuardrailsGate(approval_fn=_raises))
        result = _run_hook(adapter, "Bash", {"command": "echo hi"})
        assert result["hookSpecificOutput"]["permissionDecision"] == "deny"
        assert (
            "approval check failed"
            in result["hookSpecificOutput"]["permissionDecisionReason"]
        )

    def test_raising_approval_fn_never_reaches_safe_tools(self) -> None:
        def _raises(name: str, args: dict) -> bool:
            raise ValueError("should never be called for a SAFE tool")

        adapter = _make_adapter(GuardrailsGate(approval_fn=_raises))
        result = _run_hook(adapter, "WebSearch", {"query": "axiom"})
        assert result == {}


class TestActOptionsPermissionMode:
    """Regression test for the live-CLI-verification finding (design.md D5,
    spikes/m4-tools/spike-result.md addendum): a PreToolUse hook returning {}
    (approve) does not result in the call actually executing unless
    permission_mode="bypassPermissions" is also set. A hook `deny` still
    overrides bypassPermissions, so this does not weaken the gate."""

    def test_act_sets_bypass_permissions_mode(self) -> None:
        adapter = _make_adapter(GuardrailsGate(auto_approve=True))
        with patch.object(adapter, "_run_query", return_value="ok") as mock_run_query:
            adapter.act("do something")

        options = mock_run_query.call_args[0][1]
        assert options.permission_mode == "bypassPermissions"

    def test_act_still_wires_the_gate_hook(self) -> None:
        adapter = _make_adapter(GuardrailsGate(auto_approve=True))
        with patch.object(adapter, "_run_query", return_value="ok") as mock_run_query:
            adapter.act("do something")

        options = mock_run_query.call_args[0][1]
        assert options.hooks["PreToolUse"][0].hooks == [adapter._gate_hook]

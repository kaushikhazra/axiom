"""
Unit tests for axiom.agent.Agent's constructor-level validation, plus M10's
TurnResult/run_turn/end_session/set_provider additions.

M6 / dryrun-code-1 W1: restores the input validation the pre-M6 if/elif
provider-selection block used to provide. Kept minimal (validation-only) --
Agent's full composition (memory adapter, Router, PraoLoop) is exercised
via the e2e test suite and axiom-cli live verification instead of unit
tests here, since constructing a real Agent pulls in the full memory/
embedding stack.

M10 additions below follow the same philosophy: real Agent construction
with provider="claude" is safe and fast (ClaudeAdapter.__init__ makes no
network call -- confirmed by reading claude_adapter.py), so it's used for
wiring-level tests (does set_provider() validate/propagate correctly? does
approval_fn reach GuardrailsGate?). Actually DISPATCHING a turn
(run_turn()/run()) would need live network/auth and is deliberately not
exercised here -- that's the e2e suite's job, unchanged.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from axiom.agent import Agent, TurnResult
from axiom.memory.config import MemoryConfig
from axiom.tools.guardrails import _cli_prompt_approval


class TestProviderValidation:
    def test_invalid_provider_raises_value_error_immediately(self) -> None:
        """The check must fire before any expensive setup (persona load,
        memory adapter construction) -- confirmed by the fact this test
        doesn't require memory infra to be mocked/available."""
        with pytest.raises(ValueError, match="unknown provider"):
            Agent(provider="bogus")

    def test_empty_string_provider_raises_value_error(self) -> None:
        """Boundary case: an empty string is not None and not a valid
        choice -- must be rejected the same as any other invalid value."""
        with pytest.raises(ValueError, match="unknown provider"):
            Agent(provider="")


def _make_agent(tmp_path: Path, **kwargs) -> Agent:
    """provider='claude' keeps construction fast/network-free (no
    smolagents/Ollama import cost); an isolated tmp MemoryConfig avoids
    touching ~/.axiom/memory (matches agent.py's own docstring: "Callers
    (e.g., tests) may pass an isolated config with a tmp storage_path")."""
    cfg = MemoryConfig(storage_path=str(tmp_path / "test.surrealkv"))
    return Agent(provider="claude", memory_config=cfg, working_dir=tmp_path, **kwargs)


class TestTurnResult:
    """M10 design.md D15 -- pure dataclass, no Agent needed."""

    def test_tool_outputs_defaults_to_empty_list(self) -> None:
        result = TurnResult(text="hi")
        assert result.tool_outputs == []

    def test_default_is_not_a_shared_mutable(self) -> None:
        """dataclasses.field(default_factory=list) must give each instance
        its own list -- a bare `tool_outputs: list = []` default would leak
        appends across instances."""
        a = TurnResult(text="a")
        b = TurnResult(text="b")
        a.tool_outputs.append(("write_file", object()))
        assert b.tool_outputs == []


class TestSetProvider:
    def test_invalid_provider_raises_value_error(self, tmp_path: Path) -> None:
        agent = _make_agent(tmp_path)
        with pytest.raises(ValueError, match="unknown provider"):
            agent.set_provider("bogus")
        agent.end_session()

    def test_valid_provider_updates_router_state(self, tmp_path: Path) -> None:
        agent = _make_agent(tmp_path)
        assert agent._router.conductor_provider == "claude"
        agent.set_provider("committee")
        # "committee" only ever affects Worker selection, never Conductor
        # (Router.select_conductor()'s own rule) -- Conductor stays "claude".
        assert agent._router.conductor_provider == "claude"
        # Not exercising select_committee() here -- it would construct BOTH
        # configured adapters (claude AND local), paying the slow
        # smolagents/litellm import cost this test file otherwise avoids
        # (see module docstring). Router-level committee-selection behavior
        # is already covered by test_router.py's TestSelectCommittee; this
        # test only needs to confirm Agent.set_provider() propagated the
        # value into Router, which _forced_provider directly shows.
        assert agent._router._forced_provider == "committee"
        agent.end_session()

    def test_none_clears_the_forced_provider(self, tmp_path: Path) -> None:
        agent = _make_agent(tmp_path)  # constructed with forced provider="claude"
        assert agent._router._forced_provider == "claude"
        agent.set_provider(None)
        assert agent._router._forced_provider is None
        agent.end_session()


class TestApprovalFnForwarding:
    """dryrun-design-1 C3 / design.md D16: a naive unconditional forward of
    approval_fn=None would override GuardrailsGate's own default
    (_cli_prompt_approval) and crash axiom-cli's first DESTRUCTIVE call.
    These tests assert the actual wiring, not just the absence of a crash."""

    def test_default_agent_keeps_guardrails_gate_cli_default(
        self, tmp_path: Path
    ) -> None:
        agent = _make_agent(tmp_path)  # no approval_fn passed
        gate = agent._router.select_conductor()._gate
        assert gate._approval_fn is _cli_prompt_approval
        agent.end_session()

    def test_custom_approval_fn_reaches_guardrails_gate(self, tmp_path: Path) -> None:
        def custom_fn(tool_name: str, arguments: dict) -> bool:
            return True

        agent = _make_agent(tmp_path, approval_fn=custom_fn)
        gate = agent._router.select_conductor()._gate
        assert gate._approval_fn is custom_fn
        agent.end_session()


class TestEndSession:
    def test_idempotent(self, tmp_path: Path) -> None:
        """Mirrors faculty.shutdown()'s own idempotency (agent.py's existing
        docstring guarantee) -- a second call must not raise."""
        agent = _make_agent(tmp_path)
        agent.end_session()
        agent.end_session()  # must not raise


class TestBorrowedDependencyOwnership:
    """Post-M10 -- axiom-web builds ONE CognitiveMemoryAdapter and ONE
    ObservabilityFaculty per process and injects them into every session's
    Agent (server.py's _lifespan). Both are process-global resources: the
    adapter holds the embedding model + SurrealKV handle, the faculty holds
    the WsBridgeSink's TCP port + OTel's global TracerProvider.

    The load-bearing invariant is that a BORROWED dependency is never torn
    down by a borrower -- the first session to end would otherwise destroy it
    for every other live session. These tests pin that invariant; MagicMock
    stands in so no test pays the ~22s embedding-model load.
    """

    def test_injected_memory_adapter_is_borrowed_not_owned(
        self, tmp_path: Path
    ) -> None:
        shared = MagicMock()
        agent = _make_agent(tmp_path, memory_adapter=shared)

        assert agent._owns_memory is False
        assert agent._memory_adapter is shared

        agent.end_session()
        # Neither consolidated nor closed: that is the owner's job.
        assert shared.consolidate.call_count == 0
        assert shared.close.call_count == 0

    def test_own_memory_adapter_is_consolidated_and_closed(
        self, tmp_path: Path
    ) -> None:
        """Complement of the above -- axiom-cli's path is unchanged: an Agent
        that BUILT its adapter still tears it down on end_session()."""
        owned = MagicMock()
        with patch(
            "axiom.memory.adapter.CognitiveMemoryAdapter", return_value=owned
        ):
            agent = _make_agent(tmp_path)

        assert agent._owns_memory is True
        agent.end_session()
        assert owned.consolidate.call_count == 1
        assert owned.close.call_count == 1

    def test_injected_faculty_is_borrowed_and_never_shut_down(
        self, tmp_path: Path
    ) -> None:
        shared = MagicMock()
        shared.run_id = "run-abc"
        shared.config.trace_dir = tmp_path

        agent = _make_agent(tmp_path, faculty=shared)

        assert agent._owns_faculty is False
        assert agent._run_id == "run-abc"
        assert agent.observability_config is shared.config
        # new_run() must NOT be called: it unregisters the live run's sinks and
        # rebuilds a WsBridgeSink that cannot bind the port this one holds.
        assert shared.new_run.call_count == 0

        agent.end_session()
        assert shared.shutdown.call_count == 0

    def test_injected_faculty_wins_over_observe_flag(self, tmp_path: Path) -> None:
        """server.py pops observe/ws_port before building session_kwargs, but
        an explicit observe=True must never cause a SECOND faculty alongside an
        injected one -- that is exactly the port-conflict bug."""
        shared = MagicMock()
        shared.run_id = "run-xyz"
        shared.config.trace_dir = tmp_path

        agent = _make_agent(tmp_path, faculty=shared, observe=True)

        assert agent._faculty is shared
        assert agent._owns_faculty is False
        agent.end_session()
        assert shared.shutdown.call_count == 0

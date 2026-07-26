"""
Unit tests for GuardrailsGate (design.md §5).

Covers: classify() table (AC-02.2, AC-02.3), request_approval() approval and
denial paths via a stub approval_fn (AC-03.1, AC-03.2), auto-approve bypass
(AC-07.1, AC-07.4), and the SAFE-calls-never-prompt invariant (AC-03.5).
"""

from __future__ import annotations

from axiom.tools.guardrails import Classification, GuardrailsGate


class TestClassify:
    def test_axiom_read_file_is_safe(self) -> None:
        gate = GuardrailsGate()
        assert gate.classify("read_file") is Classification.SAFE

    def test_axiom_list_dir_is_safe(self) -> None:
        gate = GuardrailsGate()
        assert gate.classify("list_dir") is Classification.SAFE

    def test_axiom_write_file_is_destructive(self) -> None:
        gate = GuardrailsGate()
        assert gate.classify("write_file") is Classification.DESTRUCTIVE

    def test_axiom_run_shell_is_destructive(self) -> None:
        gate = GuardrailsGate()
        assert gate.classify("run_shell") is Classification.DESTRUCTIVE

    def test_claude_websearch_is_safe(self) -> None:
        gate = GuardrailsGate()
        assert gate.classify("WebSearch") is Classification.SAFE

    def test_claude_bash_is_destructive(self) -> None:
        gate = GuardrailsGate()
        assert gate.classify("Bash") is Classification.DESTRUCTIVE

    def test_claude_write_is_destructive(self) -> None:
        gate = GuardrailsGate()
        assert gate.classify("Write") is Classification.DESTRUCTIVE

    def test_claude_edit_is_destructive(self) -> None:
        gate = GuardrailsGate()
        assert gate.classify("Edit") is Classification.DESTRUCTIVE

    def test_unknown_tool_defaults_safe(self) -> None:
        gate = GuardrailsGate()
        assert gate.classify("some_future_tool") is Classification.SAFE


class TestRequestApproval:
    def test_approval_fn_true_approves(self) -> None:
        gate = GuardrailsGate(approval_fn=lambda name, args: True)
        assert gate.request_approval("run_shell", {"command": "ls"}) is True

    def test_approval_fn_false_denies(self) -> None:
        gate = GuardrailsGate(approval_fn=lambda name, args: False)
        assert gate.request_approval("run_shell", {"command": "ls"}) is False

    def test_approval_fn_receives_name_and_args(self) -> None:
        seen: dict = {}

        def _capture(name: str, args: dict) -> bool:
            seen["name"] = name
            seen["args"] = args
            return True

        gate = GuardrailsGate(approval_fn=_capture)
        gate.request_approval("write_file", {"path": "x.txt", "content": "hi"})
        assert seen == {
            "name": "write_file",
            "args": {"path": "x.txt", "content": "hi"},
        }

    def test_auto_approve_bypasses_prompt(self) -> None:
        calls: list = []

        def _should_never_be_called(name: str, args: dict) -> bool:
            calls.append((name, args))
            return False

        gate = GuardrailsGate(auto_approve=True, approval_fn=_should_never_be_called)
        assert gate.request_approval("run_shell", {"command": "ls"}) is True
        assert calls == []  # approval_fn never invoked when auto_approve=True


class TestCheck:
    def test_safe_tool_never_calls_approval_fn(self) -> None:
        calls: list = []

        def _tracking_fn(name: str, args: dict) -> bool:
            calls.append(name)
            return True

        gate = GuardrailsGate(approval_fn=_tracking_fn)
        assert gate.check("read_file", {"path": "x.txt"}) is True
        assert calls == []

    def test_destructive_tool_calls_approval_fn(self) -> None:
        calls: list = []

        def _tracking_fn(name: str, args: dict) -> bool:
            calls.append(name)
            return True

        gate = GuardrailsGate(approval_fn=_tracking_fn)
        assert gate.check("write_file", {"path": "x.txt", "content": "hi"}) is True
        assert calls == ["write_file"]

    def test_destructive_tool_denied_returns_false(self) -> None:
        gate = GuardrailsGate(approval_fn=lambda name, args: False)
        assert gate.check("run_shell", {"command": "rm -rf /"}) is False

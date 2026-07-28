"""
Unit tests for axiom.interface.web.approval_bridge (M10, design.md §5, D5,
D6; double-submit guard from dryrun-design-2 W1).
"""

from __future__ import annotations

import threading
import time

from axiom.interface.web import approval_bridge
from axiom.interface.web.approval_bridge import make_ui_approval_fn, resolve


class TestMakeUiApprovalFn:
    def test_emits_event_with_tool_name_and_arguments(self) -> None:
        events: list = []
        approval_fn = make_ui_approval_fn(events.append)

        def resolve_soon(approval_id: str) -> None:
            time.sleep(0.05)
            resolve(approval_id, True)

        # The approval_fn blocks (D6) -- resolve it from another thread,
        # same shape as the real emit_event -> frontend -> POST round trip.
        def resolve_after_emit() -> None:
            time.sleep(0.02)
            # events[0] is populated synchronously before the block, so a
            # short sleep is enough to guarantee it's there.
            resolve(events[0]["approval_id"], True)

        t = threading.Thread(target=resolve_after_emit)
        t.start()
        approved = approval_fn("write_file", {"path": "a.txt", "content": "hi"})
        t.join()

        assert approved is True
        assert len(events) == 1
        assert events[0]["type"] == "TOOL_APPROVAL_REQUEST"
        assert events[0]["tool_name"] == "write_file"
        assert events[0]["arguments"] == {"path": "a.txt", "content": "hi"}
        assert "approval_id" in events[0]

    def test_denial_returns_false(self) -> None:
        events: list = []
        approval_fn = make_ui_approval_fn(events.append)

        def resolve_after_emit() -> None:
            time.sleep(0.02)
            resolve(events[0]["approval_id"], False)

        t = threading.Thread(target=resolve_after_emit)
        t.start()
        approved = approval_fn("run_shell", {"command": "rm -rf /"})
        t.join()

        assert approved is False

    def test_timeout_denies_by_default(self) -> None:
        events: list = []
        approval_fn = make_ui_approval_fn(events.append)
        original_timeout = approval_bridge._APPROVAL_TIMEOUT_SECS
        approval_bridge._APPROVAL_TIMEOUT_SECS = 0.05
        try:
            approved = approval_fn("write_file", {"path": "a.txt"})
        finally:
            approval_bridge._APPROVAL_TIMEOUT_SECS = original_timeout
        assert approved is False

    def test_pending_entry_is_cleaned_up_after_resolution(self) -> None:
        events: list = []
        approval_fn = make_ui_approval_fn(events.append)

        def resolve_after_emit() -> None:
            time.sleep(0.02)
            resolve(events[0]["approval_id"], True)

        t = threading.Thread(target=resolve_after_emit)
        t.start()
        approval_fn("write_file", {"path": "a.txt"})
        t.join()

        assert events[0]["approval_id"] not in approval_bridge._pending


class TestResolve:
    def test_returns_false_for_unknown_approval_id(self) -> None:
        assert resolve("does-not-exist", True) is False

    def test_raises_value_error_on_double_resolve(self) -> None:
        """dryrun-design-2 W1: a second resolve() on the same approval_id
        must raise ValueError (caller maps this to HTTP 409), not let
        concurrent.futures.InvalidStateError escape as an unhandled 500.

        Deterministic (no threading race): manipulates approval_bridge's
        _pending registry directly, both resolve() calls on the same
        thread, so there's no dependency on _ui_prompt_approval's own
        background-thread finally-block pop timing."""
        from concurrent.futures import Future

        future: Future = Future()
        approval_bridge._pending["test-double-resolve"] = future
        try:
            assert resolve("test-double-resolve", True) is True
            assert future.result() is True
            try:
                resolve("test-double-resolve", True)
                raise AssertionError("second resolve() should have raised ValueError")
            except ValueError:
                pass
        finally:
            approval_bridge._pending.pop("test-double-resolve", None)

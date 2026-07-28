"""
Approval bridge — M10 (design.md §5, D5, D6): a UI-backed implementation of
GuardrailsGate's approval_fn seam (axiom/tools/guardrails.py), matching the
exact synchronous Callable[[str, dict], bool] signature the CLI's own
_cli_prompt_approval already has.

GuardrailsGate itself is NOT modified (D5) -- this module only supplies a
different approval_fn, blocking the calling thread on a
concurrent.futures.Future until the frontend resolves it via
POST /api/approval/{approval_id} (server.py), mirroring the existing
anyio.to_thread.run_sync bridge M4 already uses for the CLI's blocking
input() call.

Deployment constraint (design.md §2, dryrun-design-1 O1): _pending is an
in-process, module-level dict -- axiom-web MUST run single-process
(no `uvicorn --workers > 1`), or a second worker's disjoint _pending would
404 an approval POST routed to it instead of the worker holding the Future.
"""

from __future__ import annotations

import logging
import uuid
from concurrent.futures import Future, TimeoutError as FutureTimeoutError
from typing import Callable

logger = logging.getLogger("axiom.interface.web")

# design.md §2 -- default 300s.
_APPROVAL_TIMEOUT_SECS = 300

# approval_id -> pending Future. Single-process only (see module docstring).
_pending: dict[str, Future] = {}


def make_ui_approval_fn(
    emit_event: Callable[[dict], None],
) -> Callable[[str, dict], bool]:
    """emit_event is WebSession.emit_event (session_manager.py) -- thread-safe,
    pushes onto that session's event_queue, drained by stream_turn()
    (agui_bridge.py, D14)."""

    def _ui_prompt_approval(tool_name: str, arguments: dict) -> bool:
        approval_id = str(uuid.uuid4())
        future: Future = Future()
        _pending[approval_id] = future

        emit_event(
            {
                "type": "TOOL_APPROVAL_REQUEST",
                "approval_id": approval_id,
                "tool_name": tool_name,
                "arguments": arguments,
            }
        )

        try:
            return future.result(timeout=_APPROVAL_TIMEOUT_SECS)
        except FutureTimeoutError:
            logger.warning(
                "[UI_APPROVAL_TIMEOUT] tool=%s approval_id=%s -- denying after %ss",
                tool_name,
                approval_id,
                _APPROVAL_TIMEOUT_SECS,
            )
            return False  # denial-by-timeout -- never hangs the loop forever
        finally:
            _pending.pop(approval_id, None)

    return _ui_prompt_approval


def resolve(approval_id: str, approved: bool) -> bool:
    """Called by server.py's POST /api/approval/{approval_id} route.

    Returns True if a pending approval was found and resolved, False if
    approval_id doesn't exist (already resolved or expired -- caller
    returns 404). Raises ValueError if it exists but is already resolved
    (caller returns 409, dryrun-design-2 W1) -- a double-click, retried
    request, or Approve+Deny race would otherwise raise
    concurrent.futures.InvalidStateError as an unhandled 500.
    """
    future = _pending.get(approval_id)
    if future is None:
        return False
    if future.done():
        raise ValueError(f"approval {approval_id!r} already resolved")
    future.set_result(approved)
    return True

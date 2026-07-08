"""
Wall-clock timing utility for the PRAO loop.

Uses stdlib only (time, logging, typing). Does NOT import axiom.interfaces at runtime.
The RunState type annotation is guarded by TYPE_CHECKING so this module stays
stdlib-only and avoids any circular-import risk.

Two log variants (DEBUG level only — never stdout):
  - Success path: "[M1 Latency] %.3fs  (%d cycle(s), %d SDK spawn(s))"
  - Abort path:   "[M1 Latency] %.3fs (aborted: %s)"
"""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from axiom.interfaces import RunState

logger = logging.getLogger("axiom.observability")


def timed_run(
    loop_fn: Callable[[str], tuple[str, RunState]],
    user_input: str,
) -> tuple[str, RunState]:
    """Wrap loop_fn(user_input), emit a latency DEBUG log, and return the result.

    On success: unpacks (response_text, run_state) and logs cycle + spawn counts.
    On exception: logs elapsed time with the exception message, then re-raises.
    RunState is NOT available on the exception path (it is constructed inside
    loop.run() and only returned when loop.run() succeeds).

    Args:
        loop_fn: Callable matching the PraoLoop.run() signature.
        user_input: The user turn string to pass to loop_fn.

    Returns:
        The (response_text, run_state) tuple from loop_fn on success.

    Raises:
        Any exception raised by loop_fn — after emitting the abort-path log.
    """
    start = time.perf_counter()
    try:
        result = loop_fn(user_input)
        elapsed = time.perf_counter() - start
        _, run_state = result
        logger.debug(
            "[M1 Latency] %.3fs  (%d cycle(s), %d SDK spawn(s))",
            elapsed,
            run_state.cycle_count,
            run_state.spawn_count,
        )
        return result
    except Exception as exc:
        elapsed = time.perf_counter() - start
        logger.debug("[M1 Latency] %.3fs (aborted: %s)", elapsed, exc)
        raise

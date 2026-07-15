"""
Core contracts for the Axiom PRAO loop.

Contains:
- Intent type system (IntentKind, RespondIntent, ActIntent, FinishIntent, Intent)
- RunState value object
- Four port Protocols (PerceivePort, ReasonPort, ActPort, ObservePort)
- Exception classes (AdapterError, MaxCyclesExceededError)

All core contracts live in one module — no separate ports.py or intent.py.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Protocol, Union


# ---------------------------------------------------------------------------
# Intent type system
# ---------------------------------------------------------------------------


class IntentKind(Enum):
    RESPOND = auto()  # trivial / terminal: return text to user, end loop
    ACT = auto()  # action required: call act() with instruction
    FINISH = auto()  # explicit done signal: end loop, no response text


@dataclass(frozen=True)
class RespondIntent:
    text: str = ""
    # kind is excluded from __init__ so RespondIntent("hi") sets text, not kind.
    kind: IntentKind = field(init=False, default=IntentKind.RESPOND)


@dataclass(frozen=True)
class ActIntent:
    instruction: str = ""
    # kind is excluded from __init__ so ActIntent("do x") sets instruction, not kind.
    kind: IntentKind = field(init=False, default=IntentKind.ACT)


@dataclass(frozen=True)
class FinishIntent:
    kind: IntentKind = field(init=False, default=IntentKind.FINISH)


Intent = Union[RespondIntent, ActIntent, FinishIntent]


# ---------------------------------------------------------------------------
# Run State
# ---------------------------------------------------------------------------


@dataclass
class RunState:
    """Lightweight value object carried across loop iterations.

    Mutability decision: mutate-and-return semantics (observe() modifies in-place
    and returns self). Avoids object churn; the loop always works with the current instance.

    M3: memory_context carries the AssembledContext set by the loop at Perceive so
    perceive() can render it into the prompt without importing memory types here.
    Typed as object to avoid a circular import: interfaces.py must not import from
    axiom.memory.models. Duck-typed by base.py perceive() via .cognitive_memories
    and .working_context attributes.
    """

    user_input: str  # original user message
    history: list[str]  # accumulated act() results from prior cycles
    cycle_count: int = 0  # completed act() cycles (incremented in observe())
    spawn_count: int = (
        0  # loop-dispatched query() calls (adapter-internal retries excluded)
    )
    memory_context: object = (
        None  # M3: AssembledContext | None (typed as object to avoid memory import)
    )


# ---------------------------------------------------------------------------
# Port Protocols
# ---------------------------------------------------------------------------


class PerceivePort(Protocol):
    def perceive(self, run_state: RunState) -> str:
        """Assemble thinking input: user message + persona + prior step context."""
        ...


class ReasonPort(Protocol):
    def reason(self, context: str) -> Intent:
        """Query provider (NO tools) -> parse structured output -> return Intent.
        Sync. The adapter bridges to the async SDK internally."""
        ...


class ActPort(Protocol):
    def act(self, instruction: str) -> str:
        """Query provider (WITH tools scoped) -> execute bounded instruction -> return result.
        Sync. The adapter bridges to the async SDK internally."""
        ...


class ObservePort(Protocol):
    def observe(self, result: str, run_state: RunState) -> RunState:
        """Capture act() result and update run-state (history, cycle_count).
        Does NOT decide continue-vs-stop — that decision belongs to the loop's intent
        switch. This is a deliberate M1 decision; in M1 the loop owns all stop conditions."""
        ...


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class AdapterError(Exception):
    """Raised by any adapter method on unrecoverable SDK or subprocess failure.
    Propagates through loop.py (not caught) to agent.py (caught; converted to error string).
    """


class MaxCyclesExceededError(Exception):
    """Raised by PraoLoop.run() when cycle_count reaches max_cycles without
    a terminal intent (RESPOND or FINISH)."""

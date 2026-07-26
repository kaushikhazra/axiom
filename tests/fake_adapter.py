"""
FakeAdapter — in-memory implementation of all four PRAO port Protocols.

Second-adapter existence proof (MPP-4): confirms the port interface is implementable
without the Claude SDK. Used as the fast test enabler — no subprocess spawns,
no live SDK calls, deterministic and milliseconds-fast.

FakeMemory — in-memory stub satisfying MemoryPort. Used in tests that need to
wire PraoLoop without a real CognitiveMemoryAdapter. Returns empty AssembledContext
and records calls for assertion.
"""

from __future__ import annotations

from collections import deque

from axiom.interfaces import (
    AdapterError,
    Intent,
    RespondIntent,
    RunState,
)
from axiom.router.router import WorkerSelection
from axiom.skills.port import SkillContent, SkillNotFoundError, SkillSpec


class FakeAdapter:
    """Scripted in-memory adapter satisfying PerceivePort, ReasonPort, ActPort, ObservePort.

    Args:
        intents: Sequence of Intent objects returned from reason() in order.
                 When exhausted, returns RespondIntent(text="[FAKE] done").
        act_results: Sequence of str results returned from act() in order.
                     When exhausted, returns "[FAKE] act result".
        raise_on_reason: If True, reason() raises AdapterError on the first call
                         (for error-propagation tests).
        raise_on_act: If True, every act() call raises AdapterError (M6: for
                      RT-9 fallback tests -- pair with a second, healthy
                      FakeAdapter as the fallback worker).
    """

    def __init__(
        self,
        intents: list[Intent] | None = None,
        act_results: list[str] | None = None,
        raise_on_reason: bool = False,
        raise_on_act: bool = False,
    ) -> None:
        self._intents: deque[Intent] = deque(intents or [])
        self._act_results: deque[str] = deque(act_results or [])
        self._raise_on_reason = raise_on_reason
        self._raise_on_act = raise_on_act

        # Call-tracking lists for test assertions
        self.perceive_calls: list[RunState] = []
        self.reason_calls: list[str] = []
        self.act_calls: list[str] = []
        self.observe_calls: list[tuple[str, RunState]] = []

    # ------------------------------------------------------------------
    # PerceivePort
    # ------------------------------------------------------------------

    def perceive(self, run_state: RunState) -> str:
        self.perceive_calls.append(run_state)
        return (
            f"[FAKE context] user={run_state.user_input!r} "
            f"cycle={run_state.cycle_count}"
        )

    # ------------------------------------------------------------------
    # ReasonPort
    # ------------------------------------------------------------------

    def reason(self, context: str) -> Intent:
        self.reason_calls.append(context)
        if self._raise_on_reason:
            raise AdapterError("fake adapter reason error")
        if self._intents:
            return self._intents.popleft()
        return RespondIntent(text="[FAKE] done")

    # ------------------------------------------------------------------
    # ActPort
    # ------------------------------------------------------------------

    def act(self, instruction: str) -> str:
        self.act_calls.append(instruction)
        if self._raise_on_act:
            raise AdapterError("fake adapter act error")
        if self._act_results:
            return self._act_results.popleft()
        return "[FAKE] act result"

    # ------------------------------------------------------------------
    # ObservePort
    # ------------------------------------------------------------------

    def observe(self, result: str, run_state: RunState) -> RunState:
        self.observe_calls.append((result, run_state))
        run_state.history.append(result)
        run_state.cycle_count += 1
        return run_state


class FakeMemory:
    """In-memory stub satisfying MemoryPort — for tests that wire PraoLoop directly.

    Returns empty AssembledContext from assemble_context() and is a no-op for
    append_unit/reinforce/store. Isolates loop contract tests from the real memory layer.

    Finding-3 fix: store() is now called by the loop at RESPOND exit to persist each
    completed exchange to the cognitive tier. FakeMemory records store calls so tests
    can assert the loop wires the call correctly.
    """

    def __init__(self) -> None:
        self.appended_units: list = []
        self.reinforced_ids: list[list[str]] = []
        self.stored_calls: list[dict] = []  # records each store() invocation

    async def assemble_context(self, query: str, **kwargs):  # type: ignore[return]
        from axiom.memory.models import AssembledContext  # noqa: PLC0415

        return AssembledContext(working_context=[], cognitive_memories=[])

    async def append_unit(self, unit) -> None:
        self.appended_units.append(unit)

    async def reinforce(self, ids: list[str]) -> None:
        self.reinforced_ids.append(ids)

    async def store(
        self,
        content: str,
        memory_type: str | None = None,
        importance: float | None = None,
        tags: list[str] | None = None,
        source: str | None = None,
    ) -> str:
        import uuid  # noqa: PLC0415

        mid = str(uuid.uuid4())
        self.stored_calls.append(
            {"content": content, "memory_type": memory_type, "id": mid}
        )
        return mid


class FakeSkills:
    """In-memory stub satisfying SkillsPort -- for tests that wire PraoLoop
    directly without a real SkillsRegistry.

    Args:
        skills: Pre-populated {name: SkillContent} map served by
                list_skills()/get_skill()/search(). Empty by default (no
                skills present) -- matches SkillsRegistry's own behavior
                for a missing/empty skills_dir (SK-6).
    """

    def __init__(self, skills: dict[str, SkillContent] | None = None) -> None:
        self._skills = skills or {}
        self.list_skills_calls: int = 0
        self.get_skill_calls: list[str] = []
        self.search_calls: list[str] = []

    def list_skills(self) -> list[SkillSpec]:
        self.list_skills_calls += 1
        return [
            SkillSpec(name=c.name, description=c.description)
            for c in self._skills.values()
        ]

    def get_skill(self, name: str) -> SkillContent:
        self.get_skill_calls.append(name)
        if name not in self._skills:
            raise SkillNotFoundError(f"no such skill: {name!r}")
        return self._skills[name]

    def search(self, query: str) -> list[SkillSpec]:
        self.search_calls.append(query)
        q = query.lower()
        return [
            SkillSpec(name=c.name, description=c.description)
            for c in self._skills.values()
            if q in c.name.lower() or q in c.description.lower()
        ]


class FakeRouter:
    """In-memory stub satisfying the Router surface loop.py consumes -- for
    tests that wire PraoLoop directly without a real Router.

    Args:
        default_worker: WorkerSelection returned by select_worker() when
                         worker_selections is exhausted/not provided --
                         defaults to a fixed FakeAdapter-backed selection so
                         a bare FakeRouter() is usable with no configuration.
        worker_selections: Scripted sequence of WorkerSelection objects
                            returned from select_worker() in order (mirrors
                            FakeAdapter's `intents` pattern) -- lets a test
                            script different providers per ACT cycle (RT-3).
        fallback_selection: WorkerSelection (or None) returned by
                             select_fallback_worker() -- None means "no
                             fallback available" (RT-9's propagate-original-
                             error path).
    """

    def __init__(
        self,
        default_worker: object | None = None,
        worker_selections: list[WorkerSelection] | None = None,
        fallback_selection: WorkerSelection | None = None,
    ) -> None:
        adapter = default_worker if default_worker is not None else FakeAdapter()
        self._default_selection = WorkerSelection(
            adapter=adapter,
            provider_name="fake",
            control_level="KIND_A",
            fallback_allowed=True,
        )
        self._worker_selections: deque[WorkerSelection] = deque(worker_selections or [])
        self._fallback_selection = fallback_selection

        self.select_worker_calls: list[str] = []
        self.select_fallback_worker_calls: list[str] = []

    def select_worker(self, instruction: str) -> WorkerSelection:
        self.select_worker_calls.append(instruction)
        if self._worker_selections:
            return self._worker_selections.popleft()
        return self._default_selection

    def select_fallback_worker(self, excluded_provider: str) -> WorkerSelection | None:
        self.select_fallback_worker_calls.append(excluded_provider)
        return self._fallback_selection

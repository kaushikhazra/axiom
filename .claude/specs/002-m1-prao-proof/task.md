# M1 — PRAO Proof: Implementation Tasks

**Spec:** `002-m1-prao-proof`
**Status:** Complete

---

## Package Scaffold

- [x] Developer creates `pyproject.toml` at the project root, declaring the `axiom` package under `src/` layout, listing runtime dependencies (`claude_agent_sdk`, `anyio`) and dev dependencies (pytest), and defining the `axiom-cli` entry point pointing to `axiom.interface.cli:main`.
  _MPP-1_

- [x] Developer creates `src/axiom/__init__.py` (empty or version stub) and all required `__init__.py` stubs for `persona/`, `providers/`, `observability/`, `interface/`, and `tests/` so the package is importable.
  _MPP-1_

---

## Core Contracts (`interfaces.py`)

- [x] Developer creates `src/axiom/interfaces.py` defining: `IntentKind` enum, `RespondIntent` / `ActIntent` / `FinishIntent` frozen dataclasses, `Intent` Union alias, `RunState` mutable dataclass (fields: `user_input`, `history`, `cycle_count`, `spawn_count`), `PerceivePort` / `ReasonPort` / `ActPort` / `ObservePort` Protocols with corrected docstrings (ObservePort docstring states it does NOT decide continue-vs-stop), `AdapterError` exception, and `MaxCyclesExceededError` exception.
  _MPP-1, MPP-4_

---

## Master PRAO Loop (`loop.py`)

- [x] Developer creates `src/axiom/loop.py` implementing `PraoLoop` class: constructor takes four port-typed params (`perceive: PerceivePort`, `reason: ReasonPort`, `act: ActPort`, `observe: ObservePort`, `max_cycles: int = MAX_CYCLES`); `run(user_input: str) -> tuple[str, RunState]` constructs initial `RunState`, runs the perceive→reason→act→observe cycle, increments `run_state.spawn_count` before each `reason()` and `act()` dispatch, raises `MaxCyclesExceededError` on breach (timing.timed_run catches this and fires abort-path log before re-raising — see Observability task), returns `(intent.text, run_state)` on RESPOND and `("", run_state)` on FINISH. Zero `claude_agent_sdk` imports.
  _MPP-1, MPP-2, MPP-3_

---

## Persona Package (`persona/`)

- [x] Developer creates `src/axiom/persona/__init__.py` implementing a `load() -> str` function that reads `persona.txt` from the same package directory using `pathlib`, raises a clear error if the file is missing, and returns the persona string. Uses stdlib only.
  _MPP-6_

- [x] Developer creates `src/axiom/persona/persona.txt` containing Axiom's minimal static persona — a brief statement of purpose and voice (content decision; not a code change). Must be non-empty for MPP-6 acceptance.
  _MPP-6_

---

## Claude Adapter (`providers/claude_adapter.py`)

- [x] Developer creates `src/axiom/providers/claude_adapter.py` implementing `ClaudeAdapter.__init__(self, persona: str, allowed_tools: list[str])` storing both fields, and the `_run_query(prompt: str, options: ClaudeAgentOptions) -> str` sync bridge using `anyio.run()` wrapping a `fail_after(PER_QUERY_TIMEOUT_SECS)` async helper that iterates `sdk_query()` and returns the first `ResultMessage`'s text. `PER_QUERY_TIMEOUT_SECS = 120` constant defined at module level.
  _MPP-1_
  - [x] OQ-2 resolved: `query()` is an async generator (not a coroutine) — `async for message in sdk_query(...)` (no `await`). `ResultMessage.result` is `str | None`. `ClaudeAgentOptions(allowed_tools=[...])` confirmed correct.

- [x] Developer implements `ClaudeAdapter.perceive(run_state: RunState) -> str` assembling the structured context prompt per §7.1 (persona block + history block + current request block + intent format instruction block from §4.1), satisfying `PerceivePort`.
  _MPP-6_

- [x] Developer implements `ClaudeAdapter.reason(context: str) -> Intent` calling `_run_query(context, ClaudeAgentOptions(tools=[]))`, parsing the JSON response per §4.1 parse rules, logging `WARNING [INTENT_PARSE_FAILURE]` and attempting one bounded retry on failure, logging `WARNING [INTENT_FALLBACK]` and returning `RespondIntent(text=f"[FALLBACK_RESPOND] {raw}")` on retry failure, satisfying `ReasonPort`.
  _MPP-1, MPP-2_

- [x] Developer implements `ClaudeAdapter.act(instruction: str) -> str` calling `_run_query(bounded_prompt, ClaudeAgentOptions(allowed_tools=self._allowed_tools))` and returning the result text, satisfying `ActPort`.
  _MPP-3_

- [x] Developer implements `ClaudeAdapter.observe(result: str, run_state: RunState) -> RunState` appending `result` to `run_state.history`, incrementing `run_state.cycle_count`, and returning `run_state` (mutate-and-return), satisfying `ObservePort`.
  _MPP-3_

- [x] Developer implements error handling in `ClaudeAdapter._run_query()` catching `CLINotFoundError`, `CLIConnectionError`, `ProcessError`, `CLIJSONDecodeError`, `ClaudeSDKError`, and `TimeoutError` (anyio), logging each with a distinct `ERROR [ADAPTER_*]` marker, and re-raising as `AdapterError` per §7.6 error table.
  _MPP-1_

---

## Observability (`observability/timing.py`)

- [x] Developer creates `src/axiom/observability/timing.py` implementing a `timed_run(loop_fn, user_input: str) -> tuple[str, RunState]` wrapper that records `time.perf_counter()` before calling `loop_fn(user_input)` and emits the latency log before returning or re-raising. Two log variants: on success, emit full debug log with cycle/spawn counts; on abort, emit elapsed-only debug log then re-raise. Catches bare `Exception`. Stdlib only with `TYPE_CHECKING` guard for `RunState` annotation (`from __future__ import annotations` + `if TYPE_CHECKING: from axiom.interfaces import RunState`).
  _MPP-5_

---

## Core Assembly (`agent.py`)

- [x] Developer creates `src/axiom/agent.py` defining `M1_ALLOWED_TOOLS: list[str] = ["Bash", "WebSearch"]` (WebSearch added for M1 web-search acceptance test), `_configure_debug_logging()` (adds stderr handler at DEBUG to `"axiom"` logger), and `Agent` class whose `__init__(self, debug: bool = False)` loads persona via `persona.load()`, constructs `ClaudeAdapter(persona=..., allowed_tools=M1_ALLOWED_TOOLS)`, constructs `PraoLoop(perceive=adapter, reason=adapter, act=adapter, observe=adapter, max_cycles=10)`, and calls `_configure_debug_logging()` if `debug=True`. `Agent.run(user_input: str) -> str` calls `timing.timed_run(self._loop.run, user_input)`, catches `MaxCyclesExceededError` and `AdapterError`, returns response string or `"[Error: ...]"` string.
  _MPP-1, MPP-5, MPP-6_

---

## CLI Entry Point (`interface/cli.py`)

- [x] Developer creates `src/axiom/interface/cli.py` implementing `main()` that parses optional `--debug` flag and passes it as `Agent(debug=True)` constructor parameter, reads user input from stdin or positional argument, calls `agent.run(user_input)`, and prints the response with `if response: print(response)`. Includes a `if __name__ == "__main__": main()` guard. Imports `axiom.agent` only.
  _MPP-1, MPP-2, MPP-6_

---

## Tests

- [x] Developer creates `tests/fake_adapter.py` implementing `FakeAdapter` — an in-memory class satisfying all four Protocols (`PerceivePort`, `ReasonPort`, `ActPort`, `ObservePort`) via scripted responses. No SDK imports. Second-adapter existence proof (MPP-4) and fast-test enabler.
  _MPP-4_

- [x] Developer creates `tests/test_contracts.py` with 26 phase-port contract tests using `FakeAdapter`: (a) RESPOND short-circuit (8 tests); (b) ACT→RESPOND one cycle (7 tests); (c) MAX_CYCLES breach (4 tests); (d) `AdapterError` propagation (3 tests); (e) FINISH intent (4 tests). All 26 passed. No live SDK spawns.
  _MPP-1, MPP-2, MPP-3, MPP-4_

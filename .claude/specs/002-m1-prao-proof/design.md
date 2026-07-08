# M1 — PRAO Proof: Design

**Spec:** `002-m1-prao-proof`
**Authored:** 2026-07-07 (Velasari)
**Revised:** 2026-07-07 (Velasari — post dryrun-design-1; addresses C1–C8, W1–W6, O1–O4)
**Revised:** 2026-07-08 (Velasari — post dryrun-design-2; addresses new C1, W1, O1, O2)
**Status:** Revised draft — ready for dryrun-design-3.

---

## 1. Purpose

This document translates the M1 requirements (`requirement.md`) into concrete structural decisions: the port interfaces, the Claude adapter's internal mechanics, the control-flow of the master PRAO loop, the Intent type system, and the file layout. It supersedes `001-agent-core/architecture.md` wherever they conflict (per the requirement's own architecture note).

M1 proves exactly two things:

1. **Port-adapter seam is real** — the master loop imports zero provider code; swapping the adapter swaps the provider; the loop is untouched.
2. **Split-design latency is empirical** — every Agent SDK `query()` spawns a `claude-code` CLI subprocess. Splitting `reason()` and `act()` into separate queries means ≥ 2 spawns per cycle. M1 measures both the trivial floor (1 spawn) and a real multi-cycle task (N spawns) before M2 makes any further architectural bets.

---

## 2. Architecture Style

**Ports-and-Adapters (Hexagonal), hand-wired in Python.**

- No YAML. No declarative config. The master PRAO loop is assembled in Python code (constructor injection).
- The four PRAO phases (`perceive`, `reason`, `act`, `observe`) are each a **port** — a Python `Protocol` (structural subtyping). M1 uses `Protocol` for maximum flexibility (no forced inheritance for future adapters).
- One concrete **adapter** in M1: the `ClaudeAdapter`, backed by `claude_agent_sdk` (`query()` function + `ClaudeAgentOptions`).
- The master loop's type annotations reference the port `Protocol` types only — never the concrete `ClaudeAdapter`.

**Self-similar model.** Master agents and sub-agents are structurally identical (same loop class, same port protocols). The difference is role (which persona, which tools scope) and config — not code structure. M1 instantiates one master loop. Sub-agent dispatch is out of scope.

---

## 3. The Four Phase Ports

Defined in `src/axiom/interfaces.py`. Each is a `Protocol` with a single required method. `Intent` and `RunState` (§4, §5) are **co-located in the same module** — there is no separate `intent.py` or `ports.py`. All core contracts live in `interfaces.py`.

```python
# src/axiom/interfaces.py  (illustrative — not final code)

from typing import Protocol
# Intent and RunState are defined earlier in this same module (see §4, §5)

class PerceivePort(Protocol):
    def perceive(self, run_state: RunState) -> str:
        """Assemble thinking input: user message + persona + prior step context."""
        ...

class ReasonPort(Protocol):
    def reason(self, context: str) -> Intent:
        """Query provider (NO tools) → parse structured output → return Intent.
        Sync. The adapter bridges to the async SDK internally."""
        ...

class ActPort(Protocol):
    def act(self, instruction: str) -> str:
        """Query provider (WITH tools scoped) → execute bounded instruction → return result.
        Sync. The adapter bridges to the async SDK internally."""
        ...

class ObservePort(Protocol):
    def observe(self, result: str, run_state: RunState) -> RunState:
        """Capture act() result and update run-state (history, cycle_count).
        Does NOT decide continue-vs-stop — that decision belongs to the loop's intent
        switch. This is a deliberate M1 deviation from architecture.md's Observer/Evaluator
        role (which owns the exit criterion); in M1 the loop owns all stop conditions."""
        ...
```

**Why four protocols instead of one?** Each phase has a distinct signature and distinct contract (tool access, return type). Collapsing them into one interface would make the `ClaudeAdapter` a god-object and make future partial adapters impossible. Four lean protocols match the four-phase loop exactly.

**Design note — W3 (perceive/observe in the adapter):** In M1, `ClaudeAdapter` implements all four protocols, including `perceive()` (context assembly) and `observe()` (state bookkeeping), which `architecture.md` models as core-side components. This is intentional for M1 minimalism. At adapter #2 (e.g. vLLM), `perceive()` and `observe()` would be duplicated verbatim — these are provider-independent and expected to migrate to a shared base class or core module at that point. The four-Protocol shape already permits this migration without changing the loop.

---

## 4. The Intent Type System + Wire Format

`reason()` returns a structured **Intent** — not raw text. This is the master loop's decision signal; the loop never inspects raw model output.

**Home:** `Intent` types and `RunState` are defined in `src/axiom/interfaces.py` alongside the port Protocols — all core contracts in one module.

```python
# src/axiom/interfaces.py — Intent types section  (illustrative — not final code)

from dataclasses import dataclass
from enum import Enum, auto
from typing import Union

class IntentKind(Enum):
    RESPOND = auto()   # trivial / terminal: return text to user, end loop
    ACT     = auto()   # action required: call act() with instruction
    FINISH  = auto()   # explicit done signal: end loop, no response text

@dataclass(frozen=True)
class RespondIntent:
    kind: IntentKind = IntentKind.RESPOND
    text: str = ""

@dataclass(frozen=True)
class ActIntent:
    kind: IntentKind = IntentKind.ACT
    instruction: str = ""

@dataclass(frozen=True)
class FinishIntent:
    kind: IntentKind = IntentKind.FINISH

Intent = Union[RespondIntent, ActIntent, FinishIntent]
```

### 4.1 Intent Wire Format — Locked (JSON Envelope)

**Decision:** The intent wire format is a **strict single-line JSON envelope**. Rationale: JSON parsing is unambiguous (no prefix-collision, no case-sensitivity issues, handles special characters in payloads), and `json.loads()` gives a clear success/failure signal.

**Model instruction text** (injected verbatim into the reason prompt, after the persona and context sections):

```
---
RESPONSE FORMAT INSTRUCTIONS (mandatory):
Reply with EXACTLY ONE JSON object on a single line. No markdown. No code fences.
No explanation before or after. Only the JSON object.

Choose ONE of:
  {"intent": "RESPOND", "text": "<your response to the user>"}
  {"intent": "ACT", "instruction": "<one bounded instruction for the executor>"}
  {"intent": "FINISH"}

Rules:
- "intent" must be exactly "RESPOND", "ACT", or "FINISH" (case-sensitive).
- "RESPOND" requires a "text" field (string). Use ONLY for requests answerable from
  the conversation context or established general knowledge — no tools needed.
- "ACT" requires an "instruction" field (string). You MUST use ACT (never RESPOND)
  whenever the request requires: web search, real-time or current data, file access,
  running commands, or any side effect. Do NOT attempt to answer such requests from
  memory or training data — you have zero tools; route to ACT so the executor can act.
- STALENESS RULE: Your training knowledge may be months or years out of date. For ANY
  fact that changes over time — software/library versions, prices, who currently holds
  a role or record, news, standings, or anything phrased "latest / current / newest /
  today / now / as of" — assume your stored answer is OUTDATED and route to ACT, even
  if you feel certain. Do not answer time-varying questions from memory.
- TOOL-LESS-MEANS-DELEGATE: You (the reasoning step) have NO tools by design. This does
  not mean you cannot get live data — an executor with web search, bash, and file access
  runs whatever instruction you return in an ACT. NEVER refuse or answer directly because
  you "lack a tool"; instead route to ACT and the executor will use its tools.
- "FINISH" has no additional fields. Use it only when the task is fully complete with no response needed.
- The entire response must be parseable as a single JSON object.

Examples:
  User: "What's the capital of France?"
  → {"intent": "RESPOND", "text": "Paris."} (stable fact, no tool needed)

  User: "What's the latest stable Python version?"
  → {"intent": "ACT", "instruction": "Search the web for the latest stable Python release version."} (time-varying; stored version is likely stale)

  User: "What files are in this directory?"
  → {"intent": "ACT", "instruction": "List the files in the current directory."} (requires a tool)
---
```

**Parse rules** (inside `reason()` in the adapter):

1. Strip leading/trailing whitespace from the raw response string.
2. Parse with `json.loads()`. On `json.JSONDecodeError` or `ValueError` → parse failure (see §7.2).
3. Validate `intent` field exists and is one of `"RESPOND"`, `"ACT"`, `"FINISH"` (exact string, case-sensitive). Any other value → parse failure.
4. For `"RESPOND"`: require `text` field (str). Missing or wrong type → parse failure.
5. For `"ACT"`: require `instruction` field (str). Missing or wrong type → parse failure.
6. For `"FINISH"`: no additional fields required (extra fields ignored).
7. On success: construct and return the corresponding `Intent` dataclass.

**Multi-line payload handling:** JSON string values handle embedded newlines via `\n` escapes — no special treatment needed. The response is expected to be a single JSON line; if the model emits multi-line JSON (e.g. pretty-printed), `json.loads()` handles it correctly since it tolerates whitespace. The one failure mode is model preamble before the JSON object — caught and handled by the parse-failure path (§7.2).

---

## 5. Run State

A lightweight value object carried across loop iterations. **Mutability decision (W6):** `RunState` uses **mutate-and-return** semantics — `observe()` modifies the instance in-place and returns `self`. This avoids object churn; the loop always works with the current instance. Documented here so callers do not hold stale references between phases.

```python
@dataclass
class RunState:
    user_input: str           # original user message
    history: list[str]        # accumulated act() results from prior cycles
    cycle_count: int = 0      # completed act() cycles (incremented in observe())
    spawn_count: int = 0      # loop-dispatched query() calls (adapter-internal retries excluded — see §7.2)
```

**Field semantics:**
- `cycle_count`: counts **completed act→observe cycles** only. The "Hello" trivial path (reason→RESPOND with no act) produces `cycle_count=0`. This is intentional and correct — zero act cycles were completed.
- `spawn_count`: counts every `reason()` and `act()` call dispatched by the loop. The "Hello" path produces `spawn_count=1` (one `reason()` call). A one-cycle act task produces `spawn_count=3` (1 reason + 1 act + 1 final reason). This is the key empirical datum for MPP-5.

**Ownership of `spawn_count`:** Incremented by `PraoLoop.run()` **before** dispatching each `reason()` or `act()` call (the loop counts its own dispatches; the adapter stays dumb). The `observability/timing.py` utility receives `run_state.spawn_count` from the return value of `loop.run()` on the success path; on the abort path (`MaxCyclesExceededError` / `AdapterError`), `RunState` is not available and the timing log omits counts (see §6.2, §10).

**`final_response` removed:** This field appeared in the draft but had no owner. `loop.run()` now returns the response string directly (see §6); `final_response` is deleted from `RunState`.

**History truncation (O3):** No history truncation in M1 — deliberate. A single large `act()` output inflates subsequent `reason()` prompt tokens and latency, potentially polluting the per-cycle latency data M1 measures. Acceptable at MAX_CYCLES=10. The truncation/compression decision is deferred to M2 when the Observability milestone provides data to judge the impact.

`observe()` returns the updated `RunState`; the master loop passes it to the next `perceive()` call. Memory is out of scope — `history` is ephemeral per-session only.

---

## 6. The Master PRAO Loop — API and Control Flow

Defined in `src/axiom/loop.py`. The loop owns iteration and all stop conditions. It does not import `claude_agent_sdk` or any provider library.

### 6.1 PraoLoop Class API

```python
# src/axiom/loop.py  (illustrative — not final code)

MAX_CYCLES: int = 10  # module-level constant; overridable via constructor

class PraoLoop:
    def __init__(
        self,
        perceive: PerceivePort,
        reason: ReasonPort,
        act: ActPort,
        observe: ObservePort,
        max_cycles: int = MAX_CYCLES,
    ) -> None:
        """Four port-typed parameters — all satisfied by a single ClaudeAdapter instance in M1.
        The four-slot constructor preserves the ability to inject partial adapters in future
        milestones (e.g. a local vLLM for reason + ClaudeAdapter for act)."""
        ...

    def run(self, user_input: str) -> tuple[str, RunState]:
        """Execute the PRAO loop for one user turn.
        
        Constructs initial RunState internally. Returns (response_text, run_state).
        - response_text is the agent's reply for RESPOND exits.
        - response_text is "" for FINISH exits.
        - Raises MaxCyclesExceededError on MAX_CYCLES breach.
        - Raises AdapterError (propagated from adapter methods) on SDK failure.
        Both raised exceptions propagate to agent.py where timing.timed_run fires the
        abort-path log (elapsed only, no counts) in its except block before re-raising.
        
        The loop increments run_state.spawn_count before each reason() and act() dispatch.
        """
        run_state = RunState(user_input=user_input, history=[], cycle_count=0, spawn_count=0)
        ...
```

**Four port slots, one object in M1.** The `ClaudeAdapter` in M1 implements all four `Protocol` types, so a single instance satisfies all four constructor parameters. The four-slot constructor is not redundant — it is the composition seam that allows future milestones to inject partial adapters (e.g. use a fast local model for `reason`, keep Claude for `act`).

**Where MAX_CYCLES is injected:** Constructor parameter (default 10). `agent.py` may override when constructing the loop; no global mutation.

**Where initial RunState is constructed:** Inside `loop.run()` at the start of each turn. The caller (`agent.py`) does not construct or pre-populate `RunState`.

### 6.2 Control Flow

```
START
  │
  ▼
run_state = RunState(user_input=user_input, history=[], cycle_count=0, spawn_count=0)
  │
  ▼
perceive(run_state) ──► context: str
  │
  ▼
run_state.spawn_count += 1; reason(context) ──► intent: Intent
  │
  ├─── intent == RESPOND ──────────────────────────────────────► RETURN (intent.text, run_state)
  │
  ├─── intent == FINISH ───────────────────────────────────────► RETURN ("", run_state)
  │
  └─── intent == ACT
         │
         ▼
       run_state.spawn_count += 1; act(intent.instruction) ──► result: str
         │
         ▼
       observe(result, run_state) ──► run_state (mutated in-place)
         │
         ▼
       cycle_count < max_cycles?
         │  yes                     no
         ▼                          ▼
       (loop back to perceive)     raise MaxCyclesExceededError
                                   (timing abort-log fires in timing.timed_run — not here)
```

**Triage short-circuit (MPP-2):** When `reason()` returns `RESPOND` on the first cycle, the loop exits immediately. `act()` is never called — zero tool-related subprocess spawns. This is the natural result of the intent switch; no special code path exists for triage.

**Terminal exit contracts:**

| Exit | `loop.run()` returns | `agent.run()` returns | CLI behaviour |
|------|----------------------|-----------------------|---------------|
| RESPOND | `(intent.text, run_state)` | `intent.text` (str) | `print(response)` |
| FINISH | `("", run_state)` | `""` | `if response: print(response)` — prints nothing for FINISH |
| MAX_CYCLES breach | raises `MaxCyclesExceededError` | caught → returns error string `"[Error: max cycles exceeded]"` | `print(response)` (error message displayed) |
| Adapter error | raises `AdapterError` (propagated) | caught → returns error string `"[Error: ...]"` | `print(response)` (error message displayed) |

**Timing log on exception exits:** `agent.py` invokes `timing.timed_run(self._loop.run, user_input)` (see §10). The timing utility catches any exception from `loop.run()`, emits the abort-path log, then re-raises — so the log fires regardless of how `loop.run()` exits. However, `RunState` is constructed *inside* `loop.run()` and is only available via the return-value tuple — which does not exist when `run()` raises. Therefore two log variants exist:

- **Success path** (`RESPOND` / `FINISH`): full log `"[M1 Latency] %.3fs  (%d cycle(s), %d SDK spawn(s))"` using counts from the returned `run_state`.
- **Abort path** (`MaxCyclesExceededError` / `AdapterError`): elapsed-only log `"[M1 Latency] %.3fs (aborted: %s)"` where `%s` is the exception message. No counts — `RunState` is not accessible on the exception path.

The timing log must NOT fire inside `loop.py` — `timing.py` and `loop.py` are mutually unaware (§11 import boundary). `timing.py` catches bare `Exception` without importing `interfaces.py`.

### 6.3 Self-Correction Call-Point Stubs (W2)

`architecture.md`'s M1 table includes "Self-correction call-points: Wiring stubs only (no-op)". This design supersedes that scope item: **call-point stubs (INJECT/GATE/RECORD/CAPTURE) are deferred from M1 entirely**. Rationale: the stubs add no measurable value to the M1 structural proof; wiring named no-ops into `loop.py` before the call-point contracts are designed risks locking in a wrong call signature. M8 will introduce call-points when their contracts are known. The loop's four-phase structure leaves natural insertion seams at each phase boundary.

---

## 7. The Claude Adapter

Defined in `src/axiom/providers/claude_adapter.py`. This is the only concrete provider implementation in M1.

**SDK verified:** `claude_agent_sdk` v0.1.55. `query()` is an `async` function returning `AsyncIterator`. Tool scoping for `act()` is via `ClaudeAgentOptions(allowed_tools=[...])` — NOT as a `query(prompt=..., allowed_tools=[])` kwarg (that form does not exist in the API). The adapter bridges the sync port contract to the async SDK via `anyio.run()` per call (see §7.5).

### 7.1 `perceive()` — Context Assembly

Assembles the reasoning prompt fed to `reason()`:

```
[PERSONA]
{persona_text}

[CONVERSATION HISTORY]
{for each prior act() result in run_state.history}
  Step {n}: {result}

[CURRENT REQUEST]
{run_state.user_input}

{intent format instructions — see §4.1}
```

No memory recall. No tool catalog injection (tools are scoped at the `act()` layer, not here). This is deliberately minimal for M1.

### 7.2 `reason()` — Tool-Less Provider Query + Decision Interpretation

1. Receives the assembled context string from `perceive()`.
2. Calls the async SDK via the sync bridge (§7.5):
   ```python
   options = ClaudeAgentOptions(tools=[])       # truly tool-less: sends --tools "" to CLI
   raw_text = self._run_query(context, options) # bridges async → sync
   ```
   **Why `tools=[]` not `allowed_tools=[]`:** `subprocess_cli.py` guards `allowed_tools` with a
   truthiness check (`if self._options.allowed_tools:`), so an empty list silently skips the
   `--allowedTools` flag, leaving all CLI built-ins (including WebSearch) active. The `tools` field
   uses a `None`-check (`if self._options.tools is not None:`) with an explicit empty-list branch
   that emits `--tools ""` — the only clean SDK mechanism to deliver a genuinely tool-less spawn.
3. Parses `raw_text` per the JSON wire format rules in §4.1.
4. **On parse success:** construct and return the appropriate `Intent` dataclass.
5. **On parse failure (C2):**
   a. Log at `WARNING` with marker `[INTENT_PARSE_FAILURE]`: include the raw response and the parse error.
   b. Attempt one bounded retry: re-call the SDK with the same context plus an appended correction notice: `"Your previous response was not valid JSON. Reply with only the JSON intent object."`.
   c. Parse the retry response using the same rules.
   d. **On retry success:** return the parsed `Intent`. No additional log.
   e. **On retry failure:** log at `WARNING` with marker `[INTENT_FALLBACK]` (distinct from `[INTENT_PARSE_FAILURE]`). Return `RespondIntent(text=f"[FALLBACK_RESPOND] {raw_text}")`. The `[FALLBACK_RESPOND]` prefix in the text makes fallback responses distinguishable in the CLI output and in logs — MPP-2 and MPP-5 measurements remain honest (O1 resolved).

**One Agent SDK `query()` per `reason()` call** (two on retry; the retry `query()` also increments a separate internal counter but does NOT increment `run_state.spawn_count` — retries are adapter-internal, not loop-dispatched spawns). Rationale: `spawn_count` measures loop-dispatched calls; parse-failure retries are recovery mechanics the loop is unaware of. The retry is logged so it is visible.

**One subprocess spawn per `query()` call.**

### 7.3 `act()` — Tool-Bearing Provider Query

1. Constructs a bounded-mandate prompt that forces real tool use:
   ```
   Execute this instruction using your available tools (web search, bash, file access) and report the result.
   You have real tools — USE them. Do NOT answer from your training memory.
   For anything involving current, real-time, or time-varying information (latest versions, prices,
   who currently holds a role, news, anything phrased 'latest / current / newest / today / now'),
   you MUST perform an actual web search and ground your answer in the results — even if you believe
   you already know the answer, and never merely offer to search.
   Instruction: {instruction}
   ```
2. Calls the async SDK via the sync bridge (§7.5):
   ```python
   options = ClaudeAgentOptions(allowed_tools=self._allowed_tools)  # M1_ALLOWED_TOOLS
   result_text = self._run_query(prompt, options)
   ```
3. Returns `result_text` to `observe()`.

**`allowed_tools` source (W5):** The permitted tool list is a named constant in `agent.py`:
```python
# src/axiom/agent.py
M1_ALLOWED_TOOLS: list[str] = ["Bash", "WebSearch"]
```
`agent.py` passes this constant into `ClaudeAdapter.__init__(allowed_tools=M1_ALLOWED_TOOLS, ...)`. The adapter stores it as `self._allowed_tools`. "Bash" covers the MPP-3 exemplar task ("List files in /tmp and summarise"); "WebSearch" is required for the M1 web-search acceptance test (MPP-3/W5). The constant is the single source of truth.

**One Agent SDK subprocess per `act()` call.** The SDK's internal tool loop is the SDK's concern — Axiom writes no tool-execution harness.

**Guardrail (MPP-1 / MPP-4):** The only guardrail in M1 is `allowed_tools` scoping on this call. No mid-run intervention is possible (pre-run commitment model, per the Delegated-Agent port contract in `architecture.md`).

### 7.4 `observe()` — Result Capture + State Update

1. Appends `result` to `run_state.history`.
2. Increments `run_state.cycle_count` (tracks completed act cycles; see §5).
3. Returns `run_state` (mutated in-place; mutate-and-return semantics, see §5).

`observe()` in M1 does NOT decide continue-vs-stop — that decision lives in the loop's intent switch. `observe()` purely updates state. (In later milestones the Observer may gain an evaluation/quality-gate role; M1 keeps it minimal.)

### 7.5 Async Bridge — Sync Ports over Async SDK (C7)

**Decision:** All four port methods remain **synchronous** (`def`, not `async def`). The adapter bridges to the async `query()` function via `anyio.run()` per call. This keeps `loop.py`, `agent.py`, and the test layer all synchronous — no async infection into the core.

**Bridge pattern** (inside `ClaudeAdapter`, in `providers/claude_adapter.py`):

```python
import anyio
from claude_agent_sdk import query as sdk_query
from claude_agent_sdk.types import ClaudeAgentOptions, ResultMessage

async def _collect_query_result(prompt: str, options: ClaudeAgentOptions) -> str:
    """Async helper: run one query() call and collect the ResultMessage text."""
    result_text = ""
    async for message in await sdk_query(prompt=prompt, options=options):
        if isinstance(message, ResultMessage):
            result_text = message.result  # final result text from the subprocess
            break
    return result_text

class ClaudeAdapter:
    def _run_query(self, prompt: str, options: ClaudeAgentOptions) -> str:
        """Sync bridge: run the async helper on a fresh anyio event loop."""
        return anyio.run(_collect_query_result, prompt, options)
```

**Per-call event loop overhead:** Each `anyio.run()` call creates and tears down an event loop. This overhead is part of what M1 measures — it is included in the spawn latency data captured by `observability/timing.py`. M1's latency numbers reflect real end-to-end cost including the async bridge.

**Chunk collection:** The SDK `query()` async generator yields multiple message types (`AssistantMessage`, `SystemMessage`, `ResultMessage`, etc.). The adapter iterates and stops at the first `ResultMessage`, which carries the subprocess's final text output. Intermediate messages (thinking, tool calls) are discarded in M1 — no streaming to the CLI in this milestone.

**`anyio` is an existing dependency** of `claude_agent_sdk` (confirmed: `Requires: anyio, mcp`). No new package is added for the bridge.

**Per-query timeout:** Wrap the async helper with `anyio.fail_after(PER_QUERY_TIMEOUT_SECS)`. Constant defined in `claude_adapter.py`:
```python
PER_QUERY_TIMEOUT_SECS: int = 120  # 2 minutes; CLI process can hang if unauthenticated
```
On timeout, `anyio.fail_after()` raises `TimeoutError`, which the adapter catches and re-raises as `AdapterError` (see §7.6).

### 7.6 Error Handling (C3)

**`AdapterError`** — defined in `interfaces.py` (co-located with the port contracts):
```python
class AdapterError(Exception):
    """Raised by any adapter method on unrecoverable SDK or subprocess failure.
    Propagates through loop.py (not caught) to agent.py (caught; converted to error string).
    """
```

**Error scenarios and adapter behaviour:**

| Scenario | SDK exception | Adapter action |
|----------|---------------|----------------|
| CLI not installed | `CLINotFoundError` | Log `ERROR [ADAPTER_CLI_NOT_FOUND]`; raise `AdapterError("claude-code CLI not found: install and authenticate first")` |
| CLI not authenticated | `CLIConnectionError` | Log `ERROR [ADAPTER_CLI_AUTH_FAIL]`; raise `AdapterError("claude-code CLI connection failed: check authentication")` |
| Subprocess crash / non-zero exit | `ProcessError` | Log `ERROR [ADAPTER_PROCESS_ERROR]` with exit code; raise `AdapterError(...)` |
| JSON decode error from subprocess | `CLIJSONDecodeError` | Log `ERROR [ADAPTER_JSON_ERROR]`; raise `AdapterError(...)` |
| Any other `ClaudeSDKError` | `ClaudeSDKError` | Log `ERROR [ADAPTER_SDK_ERROR]`; raise `AdapterError(str(e))` |
| Query timeout (> 120s) | `TimeoutError` (anyio) | Log `ERROR [ADAPTER_TIMEOUT]`; raise `AdapterError("query timed out after 120s")` |
| Empty `ResultMessage` text | (no exception, empty str) | Return `""` — treated as a valid (empty) response. The loop's RESPOND path returns empty text to the user; the caller (CLI) prints it. Not an error. |
| SDK run failed (`ResultMessage.is_error=True`) | (no exception; terminal `ResultMessage` with `is_error=True`) | Log `ERROR [ADAPTER_SDK_IS_ERROR]` with `subtype` and `errors` detail; raise `AdapterError("SDK run failed (...)")`. No empty return. |
| Any other `Exception` (unhandled, non-`AdapterError`) | Any `Exception` subclass not matched above | Log `ERROR [ADAPTER_UNEXPECTED]`; raise `AdapterError("unexpected error: {e}")`. `BaseException` subclasses (`KeyboardInterrupt`, `SystemExit`) pass through uncaught. |

**Error propagation path:** `AdapterError` raised in `reason()` or `act()` propagates through `loop.py` (not caught there — the loop is dumb) to `timing.timed_run` (called by `agent.py`). `timing.timed_run` catches the exception, emits the elapsed-only abort log `"[M1 Latency] %.3fs (aborted: %s)"`, then re-raises. `agent.py` catches `AdapterError` and `MaxCyclesExceededError` (re-raised by `timed_run`) in an outer `except` block and returns a user-visible error string `"[Error: {message}]"`. The CLI then prints this string via `print(response)`. The loop never hangs — `AdapterError` terminates the turn immediately (MPP-1 satisfied).

---

## 8. The Reason/Act Fusion Seam (Critical Design Point)

The Claude Agent SDK **naturally fuses** reason and act: given a prompt with tools, the model decides what to do AND executes it in the same `query()` call. M1's Claude adapter deliberately **splits** them:

- `reason()` → tool-less query → intent only
- `act()` → tool-bearing query → execution

**Why split matters for M1's proof:**

If we fused (one `query()` with tools), we would be running the SDK's internal PRAO loop — not ours. The master loop would become a thin wrapper with no real phase control. The port-adapter seam would be nominal, not structural.

By splitting, the master loop owns the iteration. Each phase transition is explicit code in `loop.py`. The port interfaces are exercised as real contracts, not passthrough facades. This is what M1 must prove.

**The latency tax:** Splitting means ≥ 2 subprocess spawns per reason→act cycle. The fused path is 1 spawn. M1 measures both the trivial path (1 spawn via short-circuit) and the multi-cycle path (N×2 spawns) so this cost is data before M2 builds on top.

**Future lever (captured, not built — MPP-5):** Because `reason()` uses no tools, it could later be replaced with a direct Client-SDK API call (no subprocess) to eliminate the subprocess overhead for the reason phase. This reduces the split tax from 2 spawns per cycle to 1 spawn (act only). This optimisation is explicitly out of scope for M1 but the seam is here: `ReasonPort.reason()` has a clean interface; the adapter implementation is the only thing that would change.

**Watch point when adding a non-SDK provider (e.g. local vLLM):** A local completion model has no internal tool loop. The `act()` implementation for such a provider must supply its own tool-execution harness. The `ActPort` contract remains the same; the adapter complexity moves inward. This is the seam to watch.

---

## 9. Persona

Persona is **internal to Axiom** — it is NOT a CLI / interface concern.

- **Package:** `src/axiom/persona/` — contains the persona loader (`__init__.py` or `loader.py`) and the static content (`persona.txt`).
- **Loaded once** at composition time by the core assembly (`src/axiom/agent.py`), passed into `ClaudeAdapter.__init__()`.
- **Injected** into every `reason()` prompt via `perceive()` as a static string.
- No mutation, no persistence, no dynamic update logic in M1.
- Changing the persona = editing `persona.txt`. Zero code changes.

The `interface/` CLI package (entry point) calls `agent.run(user_input)` and receives a response string. It **never** touches, loads, or knows about the persona.

M1 persona will reflect Axiom's identity (e.g. a brief statement of purpose and voice). Exact text is a content decision, not a design decision.

---

## 10. Latency Measurement

Latency is a first-class M1 output, not a debug afterthought.

**What is measured:** Wall-clock elapsed time for the full session — from the moment the loop starts (`time.perf_counter()`) to the moment the final response is produced (or the error path completes).

**Who measures it:** The `observability/` package (`src/axiom/observability/timing.py`). The core assembly (`agent.py`) invokes `timing.timed_run(self._loop.run, user_input)`, which catches any exception from `loop.run()`, emits the appropriate log variant (full on success, elapsed-only abort on exception), then re-raises — so the log fires regardless of the exit path. The `interface/` CLI package does **not** measure anything.

**`spawn_count` transport (C4):** `loop.run()` returns `tuple[str, RunState]`. `timing.timed_run` unpacks `run_state.spawn_count` from the return tuple on the success path. On the abort path (`MaxCyclesExceededError` / `AdapterError`), `RunState` is not available — the timing utility emits an elapsed-only abort variant instead (see §6.2). The adapter is never consulted for counts — the loop is the counter (see §5, §6).

**What is reported:** After each run, latency is emitted via Python stdlib **`logging`** at **`DEBUG` level only** — never to stdout, and not at `INFO` or `ERROR` level. Two variants depending on exit path:

**Success path** (`RESPOND` / `FINISH`):
```python
logger.debug(
    "[M1 Latency] %.3fs  (%d cycle(s), %d SDK spawn(s))",
    elapsed, run_state.cycle_count, run_state.spawn_count,
)
```

**Abort path** (`MaxCyclesExceededError` / `AdapterError`):
```python
logger.debug("[M1 Latency] %.3fs (aborted: %s)", elapsed, exc)
```

Where `run_state` is unpacked from the `loop.run()` return tuple on the success path only; on the abort path `RunState` is not available (constructed inside `loop.run()`, not returned when it raises). Example for the "Hello" path: `[M1 Latency] 2.341s  (0 cycle(s), 1 SDK spawn(s))` — zero act cycles, one reason spawn.

**Note on retry spawns (W1):** `spawn_count` counts loop-dispatched `query()` calls only (adapter-internal retries excluded — see §7.2). Any run that emits a `[INTENT_PARSE_FAILURE]` warning contains one additional adapter-internal retry spawn not reflected in `spawn_count`. When cross-referencing latency against spawn count during M1 sign-off, check for `[INTENT_PARSE_FAILURE]` in the WARNING log to detect this case.

**DEBUG log handler configuration (W4):** The `axiom` logger is not configured by default (root logger defaults to WARNING). `agent.py` configures a stderr handler at DEBUG level, opt-in via the `debug=True` **constructor parameter** (constructor parameter — not a process-global mutation):

```python
# src/axiom/agent.py
import logging

_axiom_logger = logging.getLogger("axiom")

def _configure_debug_logging() -> None:
    """Configure axiom logger to emit DEBUG records to stderr. Call once at startup."""
    handler = logging.StreamHandler()   # writes to sys.stderr
    handler.setLevel(logging.DEBUG)
    _axiom_logger.setLevel(logging.DEBUG)
    _axiom_logger.addHandler(handler)

# Called in Agent.__init__(debug=True). cli.py passes Agent(debug=True) when --debug flag is set.
```

The latency `logger.debug(...)` line in `timing.py` uses `logging.getLogger("axiom.observability")`, which is a child of `"axiom"` and inherits the handler. The CLI exposes `--debug` as an optional flag; `cli.py` passes `Agent(debug=True)` when it is set. Without `--debug`, the DEBUG record is silently dropped — normal CLI output is uncluttered.

**M1 acceptance sign-off retrieval:** Run with `python -m axiom.interface.cli --debug` (cli.py includes a `if __name__ == "__main__": main()` guard so `-m` invocation works); the latency line appears on stderr after each turn. No persistent storage; no formal dashboard.

Rationale for DEBUG level: retained for debugging later without cluttering normal CLI output. **Future option (M2 Observability, not M1):** replace stdlib logging with `structlog` for structured/machine-readable traces — that belongs to the M2 Observability milestone. M1 uses stdlib logging only.

**Two target scenarios to capture in M1 acceptance:**

| Scenario | Expected `spawn_count` | Expected `cycle_count` | Latency target |
|---|---|---|---|
| "Hello" (trivial, short-circuit) | 1 (`reason()` only) | 0 (no act cycles) | TBD — measured in M1 |
| Real task ("List files in /tmp and summarise") | ≥ 3 (1 reason + 1 act + 1 final reason) | ≥ 1 | TBD — measured in M1 |

---

## 11. File Layout

M1 maps to the **canonical package-per-component structure** locked in the roadmap (2026-07-04). No new layout is introduced — modules slot into the existing `src/axiom/` packages.

```
axiom/
├── src/
│   └── axiom/
│       ├── __init__.py
│       ├── interfaces.py          # Core contracts: PerceivePort, ReasonPort, ActPort, ObservePort (Protocols)
│       │                          #   + Intent type system (IntentKind, RespondIntent, ActIntent, FinishIntent, Intent)
│       │                          #   + RunState
│       │                          #   + AdapterError, MaxCyclesExceededError
│       ├── loop.py                # PraoLoop class (imports interfaces only; zero provider imports)
│       │                          #   + MAX_CYCLES module constant
│       ├── agent.py               # Core assembly / composition root:
│       │                          #   + M1_ALLOWED_TOOLS constant
│       │                          #   + wires persona (from persona/) + ClaudeAdapter (from providers/)
│       │                          #   + constructs PraoLoop with four port slots
│       │                          #   + wraps loop.run() via the observability timing utility (timing.timed_run)
│       │                          #   + configures axiom logger when debug=True constructor param is set
│       │                          #   + exposes: run(user_input: str) -> str
│       ├── persona/
│       │   ├── __init__.py        # Persona loader (reads persona.txt, exposes load() -> str)
│       │   └── persona.txt        # Static persona content
│       ├── providers/
│       │   ├── __init__.py
│       │   └── claude_adapter.py  # ClaudeAdapter: implements all four port Protocols via claude_agent_sdk
│       │                          #   + PER_QUERY_TIMEOUT_SECS constant
│       │                          #   + _run_query() sync bridge (anyio.run per call)
│       │                          #   + parse-failure retry + [INTENT_PARSE_FAILURE] / [INTENT_FALLBACK] logging
│       │                          #   + error handling: AdapterError wraps all SDK exceptions
│       ├── observability/
│       │   ├── __init__.py
│       │   └── timing.py          # Wall-clock timer utility; try/finally around loop.run(); emits DEBUG log
│       └── interface/
│           ├── __init__.py
│           └── cli.py             # Pure I/O entry point: reads input, calls agent.run(), prints response
│                                  #   + --debug flag → passes to agent for debug logging config
├── tests/
│   ├── __init__.py
│   ├── fake_adapter.py            # FakeAdapter: in-memory implementation of all four Protocols
│   │                              #   (second-adapter existence proof; enables fast unit tests)
│   └── test_contracts.py          # Phase-port contract tests (use FakeAdapter, not live SDK)
├── pyproject.toml                 # Package metadata; dependencies: claude_agent_sdk, anyio
└── .claude/
    └── specs/002-m1-prao-proof/
        ├── requirement.md
        ├── design.md               # ← this document
        └── task.md                 # ← implementation checklist
```

**Dependency / import rules (enforced at import level):**

| Module | May import |
|---|---|
| `loop.py` | `axiom.interfaces` only — zero provider imports |
| `providers/claude_adapter.py` | `axiom.interfaces`, `claude_agent_sdk`, `anyio` |
| `persona/__init__.py` | stdlib only (pathlib, etc.) |
| `observability/timing.py` | stdlib only (time, logging) |
| `agent.py` (composition root) | `axiom.loop`, `axiom.providers.claude_adapter`, `axiom.persona`, `axiom.observability.timing`, `axiom.interfaces` (for error types), stdlib |
| `interface/cli.py` | `axiom.agent` only — never imports loop, adapter, persona, or observability directly |
| `tests/fake_adapter.py` | `axiom.interfaces` only |
| `tests/test_contracts.py` | `axiom.interfaces`, `axiom.loop`, `tests.fake_adapter` |

No circular imports. The port-adapter proof is confirmed by `loop.py` importing zero provider code.

**Test strategy (O2):** `FakeAdapter` in `tests/fake_adapter.py` is an in-memory implementation of all four Protocols. It is both the second-adapter existence proof (MPP-4: "a second adapter could be written") and the fast-test enabler — contract tests run without spawning a live SDK subprocess. `FakeAdapter` is scripted: given a sequence of inputs, it returns pre-configured Intents and act results. This makes PRAO cycle tests deterministic and milliseconds-fast.

**Naming reconciliation:** the roadmap calls the contracts file `interfaces.py`; earlier drafts called it `ports.py`. **`interfaces.py` is canonical** — locked by the roadmap's Code Structure section (2026-07-04).

---

## 12. System Diagram

```
  User input             ┌──────────────────────────────────────────────────┐
  (stdin / arg) ────────►│  interface/cli.py  (pure I/O entry point)        │
                         │  • reads input; optional --debug flag            │
                         │  • calls agent.run(user_input) -> str            │
                         │  • if response: print(response)                  │
                         └────────────────┬─────────────────────────────────┘
                                          │
                                          ▼
                         ┌──────────────────────────────────────────────────┐
                         │  agent.py  (core assembly / composition root)    │
                         │  • M1_ALLOWED_TOOLS = ["Bash", "WebSearch"]      │
                         │  • loads persona; constructs ClaudeAdapter       │
                         │  • constructs PraoLoop(perceive=adapter,         │
                         │      reason=adapter, act=adapter,                │
                         │      observe=adapter, max_cycles=10)             │
                         │  • wraps loop.run() via timing.timed_run         │
                         │  • (response, run_state) = timed_run (success)   │
                         │  • catches MaxCyclesExceededError, AdapterError  │
                         └──────┬────────────────────┬───────────────────────┘
                                │                    │
                                │                    ▼
                                │  ┌─────────────────────────────────────────┐
                                │  │  observability/timing.py                │
                                │  │  • perf_counter() start/stop            │
                                │  │  • success: debug("[M1 Latency] %.3fs   │
                                │  │    (%d cycle(s), %d SDK spawn(s))",     │
                                │  │    elapsed, run_state.cycle_count,      │
                                │  │    run_state.spawn_count)               │
                                │  │  • abort:   debug("[M1 Latency] %.3fs   │
                                │  │    (aborted: %s)", elapsed, exc)        │
                                │  │    → re-raise (RunState not available)  │
                                │  └─────────────────────────────────────────┘
                                │
                                ▼
                         ┌──────────────────────────────────────────────────┐
                         │  loop.py — PraoLoop                              │
                         │                                                  │
                         │  run_state = RunState(user_input, [], 0, 0)      │
                         │                                                  │
                         │  perceive(run_state) → context: str              │
                         │       │                                          │
                         │  run_state.spawn_count += 1                      │
                         │  reason(context) → Intent                        │
                         │       │                                          │
                         │       ├── RESPOND → return (intent.text, state)  │
                         │       ├── FINISH  → return ("", state)           │
                         │       └── ACT                                   │
                         │             run_state.spawn_count += 1           │
                         │             act(intent.instruction) → result     │
                         │             observe(result, state) → state       │
                         │             cycle_count >= max? → raise          │
                         │             MaxCyclesExceededError               │
                         │             else → (loop back to perceive)      │
                         └──────────┬───────────────────────────────────────┘
                                    │  (via PerceivePort / ReasonPort /
                                    │   ActPort / ObservePort in interfaces.py)
                                    ▼
                         ┌──────────────────────────────────────────────────┐
                         │  providers/claude_adapter.py — ClaudeAdapter     │
                         │                                                  │
                         │  perceive()  ► assemble context string           │
                         │                (persona + history + request      │
                         │                 + intent format instructions)    │
                         │                                                  │
                         │  reason()    ► options = ClaudeAgentOptions(     │
                         │                  tools=[])                       │
                         │               ► _run_query(context, options)     │
                         │                  [anyio.run() sync bridge]       │
                         │               ► json.loads(raw_text) → Intent    │
                         │                  [parse failure → retry/fallback]│
                         │                                                  │
                         │  act()       ► options = ClaudeAgentOptions(     │
                         │                  allowed_tools=self._allowed_tools│
                         │                )  [M1_ALLOWED_TOOLS from agent]  │
                         │               ► _run_query(prompt, options)      │
                         │                  [anyio.run() sync bridge]       │
                         │                                                  │
                         │  observe()   ► history.append(result)            │
                         │               ► cycle_count += 1                 │
                         │               ► return run_state (mutated)       │
                         │                                                  │
                         │  _run_query(): anyio.run(_collect_query_result,  │
                         │    prompt, options)                               │
                         │    — fail_after(PER_QUERY_TIMEOUT_SECS=120)      │
                         │    — SDK exceptions → AdapterError               │
                         └──────────────────────┬───────────────────────────┘
                                                │
                                                ▼
                         ┌──────────────────────────────────────────────────┐
                         │  claude_agent_sdk.query()  [async]               │
                         │  • prompt: str                                   │
                         │  • options: ClaudeAgentOptions(tools=[])         │
                         │    or ClaudeAgentOptions(allowed_tools=[...])    │
                         │  • yields: AssistantMessage, SystemMessage,      │
                         │            ResultMessage, ...                    │
                         │  • adapter collects ResultMessage.result (text)  │
                         └──────────────────────┬───────────────────────────┘
                                                │  spawns subprocess
                                                ▼
                         ┌──────────────────────────────────────────────────┐
                         │  claude-code CLI subprocess                      │
                         │  (one per query() call)                          │
                         │  • reason() spawn: no tools, intent JSON output  │
                         │  • act() spawn:    tool-bearing, SDK-managed     │
                         │                    internal tool loop            │
                         └──────────────────────────────────────────────────┘
```

---

## 13. Requirements Traceability

| Story | Satisfied by |
|---|---|
| **MPP-1** — PRAO loop runs end-to-end via Claude adapter | `PraoLoop` in `loop.py` + `ClaudeAdapter` implementing all four port Protocols. `loop.py` imports zero `claude_agent_sdk` code — confirmed by import boundary rule. `AdapterError` propagates to `agent.py` and is converted to error string; the loop never hangs (timeout at 120s per query). |
| **MPP-2** — Trivial input short-circuits at `reason()`, no `act()` spawned | Natural result of intent switch: `RESPOND` exits before `act()`. Parse-failure fallback `[FALLBACK_RESPOND]` is distinguishable in logs from genuine `RESPOND` via `[INTENT_FALLBACK]` marker — measurement remains honest (O1). |
| **MPP-3** — Tool-requiring task drives full reason → act → observe cycle | `ACT` intent triggers `act()` with `M1_ALLOWED_TOOLS`; `observe()` captures result into `run_state.history`; loop continues until `RESPOND`/`FINISH` or `MaxCyclesExceededError`. |
| **MPP-4** — Provider adapter is a drop-in; master loop untouched for a second adapter | Four Protocols in `interfaces.py`; `ClaudeAdapter` is the only concrete implementation; `PraoLoop` constructor takes port-typed params, not concrete types. `FakeAdapter` in `tests/fake_adapter.py` is the second-adapter existence proof — confirms the port is implementable by a non-SDK adapter. |
| **MPP-5** — M1 measures and reports latency (Hello floor + real task) | `observability/timing.py` wraps `loop.run()` via `timed_run`; emits full `logger.debug("[M1 Latency] ...", elapsed, cycle_count, spawn_count)` on success, elapsed-only abort variant on exception (counts not available on exception path — see §6.2, §10). `spawn_count` carried in `RunState` returned by `loop.run()` on success. Debug log retrievable via `--debug` flag (`cli.py` passes `Agent(debug=True)`; stderr handler configured in `agent.py`). |
| **MPP-6** — Agent carries a minimum static persona | `persona/` package loads `persona.txt`; persona string passed into `ClaudeAdapter.__init__()` by `agent.py`; injected into every `reason()` prompt via `perceive()`. CLI (`interface/cli.py`) never touches persona. |

---

## 14. Open Questions

| # | Question | Status |
|---|----------|--------|
| OQ-1 | **`M1_ALLOWED_TOOLS` list adequacy:** "Bash" is the initial allowlist. If the MPP-3 acceptance task requires file-read or glob tools, add them to the constant before sign-off. One-line change in `agent.py`. | Resolve at sign-off testing. |
| OQ-2 | **`query()` call shape and `ResultMessage.result` attribute name:** Confirm, against the installed SDK source, the exact `query()` call shape (`await`-then-iterate vs direct `async for`) AND the `ResultMessage` result attribute name. The `_collect_query_result` helper currently writes `async for message in await sdk_query(...)` and accesses `message.result` — both are illustrative and marked not final. Both land in the same verification step, contained to `_collect_query_result()`, and fail loudly on the first live call. | Confirm during implementation of `claude_adapter.py`. |

**Deferral status:** OQ-1 and OQ-2 are ACCEPTED design-time deferrals — each is verified at implementation, fails loudly on the first live call, and is contained to a single function (`agent.py` constant and `_collect_query_result()` respectively). Closed-by-decision, not open gaps.

---

## 15. Out of Scope (restate for design clarity)

The following are explicitly NOT designed or built in M1:

- **Memory** — no cross-session recall; `RunState.history` is ephemeral.
- **Observability** — M2 concern; M1 timing is wall-clock via stdlib `logging` at DEBUG level only (no structured trace, no dashboard). `structlog` / machine-readable traces are a M2 option.
- **Tools registry / Skills** — M1 passes `allowed_tools` to the SDK; no Axiom-owned registry.
- **Full guardrail policy** — only `allowed_tools` scoping on `act()`.
- **Router / multi-provider selection** — one adapter, wired in `agent.py`. *Note (O4): `agent.py`'s fixed wiring of a single `ClaudeAdapter` IS the M1 Router stub. The Router grows into a full policy engine at M6.*
- **Sub-agent dispatch / Orchestrator** — single master loop; self-similar model proven at the structural level only.
- **Dynamic / evolving persona** — static file; no mutation.
- **YAML / declarative config** — Python wiring only.
- **Web interface** — CLI only.
- **Client-SDK direct call for `reason()`** — latency optimisation, noted as a future lever (Section 8), out of scope for M1.
- **Self-correction call-point stubs** — deferred from M1 (see §6.3). M8 concern. The loop's four-phase structure leaves natural insertion seams.
- **Connectors** — M9 concern.

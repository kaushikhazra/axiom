# Design Dry-Run Report #1

**Document**: `.claude/specs/002-m1-prao-proof/design.md`
**Reviewed**: 2026-07-07
**Also read**: `requirement.md` (same spec), `task.md` (same spec — exists but EMPTY), `.claude/specs/001-agent-core/architecture.md`

---

## Critical Gaps (must fix before implementation)

### [C1] Intent wire format is unspecified — the Decision-Interpreter contract is an "e.g."
- **Pass**: Pass 3 (Interface Contract Validation)
- **What**: §4 says the adapter instructs the model to produce "a JSON envelope **or** a clearly delimited response format"; §7.2 gives only examples (`RESPOND: <text>`, `ACT: <instruction>`, `FINISH`). The actual format — JSON vs prefix-delimited, exact grammar, multi-line `text`/`instruction` handling, what happens when the model emits `RESPOND:` mid-response, case sensitivity — is never decided. This is the single most load-bearing contract in M1 (the loop's entire decision signal) and an implementer must invent it.
- **Risk**: The parse layer gets improvised; format drift between the prompt instruction and the parser causes intermittent misclassification (ACT parsed as RESPOND), which silently terminates multi-cycle tasks (breaks MPP-3) and corrupts the latency data M1 exists to gather.
- **Fix**: Lock the exact format in §4/§7.2 (recommend: single-line prefix grammar with explicit rules for multi-line payloads, or a strict JSON schema), including the exact instruction text pattern given to the model and the exact parse rules.

### [C2] Parse-failure fallback contradicts "strict parsing" and swallows failures on the ACT path
- **Pass**: Pass 5 (Failure Path Analysis)
- **What**: §7.2 step 3 says "Parsing is strict: unrecognised output defaults to `RespondIntent` with the raw text, to avoid silent failures." This is self-contradictory: a lenient default IS a silent failure. If the model intended ACT but formatted it badly, the raw (possibly instruction-like) text is returned to the user as the final answer and the loop exits — no log, no retry, no marker distinguishing a parsed RESPOND from a fallback RESPOND.
- **Risk**: MPP-3 runs can end after zero act() calls with garbage output, and nobody can tell from the logs whether the short-circuit was genuine triage or a parse failure — invalidating both the MPP-2 and MPP-5 measurements.
- **Fix**: Specify the failure path explicitly: at minimum, log the parse failure (WARNING or DEBUG with a distinct marker) and decide whether fallback-to-RESPOND is acceptable or whether one bounded re-ask/retry is performed. State the decision and its rationale in §7.2.

### [C3] No failure path for the Agent SDK / subprocess layer anywhere in the design
- **Pass**: Pass 5 (Failure Path Analysis)
- **What**: Every `reason()` and `act()` call spawns a `claude-code` CLI subprocess (§7.2/§7.3, §12). The design specifies zero behaviour for: CLI not installed / not authenticated (a stated infrastructure dependency in requirement.md), subprocess crash or non-zero exit, SDK exception, timeout/hang, or an **empty** final text result from `query()`. `act()` returning an empty string flows into `observe()` and `history` with no defined handling; a hung subprocess violates MPP-1's "returns control to the CLI without hanging" AC with no timeout defined.
- **Risk**: The first environmental hiccup produces an unhandled traceback through `loop.py` → `agent.py` → raw stack trace on the CLI, or an infinite hang. Blast radius is the whole session.
- **Fix**: Add an error-handling section: define what the adapter does on SDK exception / empty output (raise a typed adapter error? return an error-carrying Intent/result?), whether a per-query timeout exists and its value, and how the loop/agent.py surfaces the error to the CLI.

### [C4] `spawn_count` has no owner and no path to `timing.py`
- **Pass**: Pass 2 (Data Flow Trace)
- **What**: §10 defines `spawn_count = reason() calls + act() calls` and shows it in the DEBUG log emitted by `observability/timing.py`, which merely "wraps `loop.run()`". But nothing in the design creates or transports this datum: the adapter makes the SDK calls, the loop doesn't count them, `RunState` has no spawn field, and `loop.run()`'s return type is undefined. Same problem for `cycle_count` reaching the log line. Per §11's import rules, `timing.py` imports stdlib only — it cannot reach into the adapter.
- **Risk**: The key empirical datum of the entire milestone (MPP-5) is designed as a log field with no producer. Implementer will bolt on an ad-hoc counter (adapter instance attribute? loop return tuple?) — each option has different port-contract implications.
- **Fix**: Decide and document: e.g. `RunState` gains `spawn_count` incremented by the loop on each reason()/act() dispatch (keeps the adapter dumb), and `loop.run()` returns `(response, run_state)` so `agent.py` can hand counts to the timing utility.

### [C5] `loop.run()` and the loop's constructor contract are undefined
- **Pass**: Pass 3 (Interface Contract Validation)
- **What**: §6 gives control flow but never the API: Does the loop take four separate port objects or one object satisfying all four Protocols? (§11 says `ClaudeAdapter` "implements all four port Protocols" — one object — but MPP-4's drop-in claim and §3's "future partial adapters" rationale imply four injectable slots.) What is `run()`'s signature and return type? Where does the initial `RunState` get constructed, and by whom (loop or agent.py)? Where does MAX_CYCLES get injected?
- **Risk**: This is the composition-root seam MPP-4 is graded on. Two implementers produce incompatible wirings; a "one adapter object" signature quietly forecloses the partial-adapter future §3 argues for.
- **Fix**: Specify the loop class: constructor parameters (recommend four port-typed params, all satisfied by the same ClaudeAdapter instance in M1), `run(user_input: str) -> ...` signature, initial-RunState construction, and MAX_CYCLES injection point.

### [C6] Terminal-path return contracts undefined: FINISH-with-no-text, MAX_CYCLES abort, and who sets `final_response`
- **Pass**: Pass 4 (State Machine & Transitions)
- **What**: Three loop exits have no defined output contract against `agent.run(user_input) -> str`:
  1. **FINISH** — "RETURN (no response text)" (§6). What string does `agent.run()` return? What does the CLI print — empty line, nothing, a canned "Done."?
  2. **MAX_CYCLES breach** — "aborts with an error delivered to the CLI" (§6). Delivered how? Exception (of what type, importable from where, given `cli.py` may import `axiom.agent` only)? Error string return? The timing log must still fire on this path — unstated.
  3. **`RunState.final_response`** (§5) is "populated on RESPOND intent" — by whom? The loop's intent switch, or `observe()`? `observe()` is never called on the RESPOND path per §6, so if observe owns it, it's never set.
- **Risk**: Three of the loop's four exit states are guesswork; the CLI contract ("pure I/O") can't be implemented without inventing behaviour, and `final_response` risks being dead data (created, never written).
- **Fix**: Define the return value for each exit path, the MAX_CYCLES error-delivery mechanism (recommend: typed exception caught in `agent.py`, converted to an error string), and assign `final_response` ownership to the loop's RESPOND branch (or delete the field).

### [C7] Port signatures are sync; the Claude Agent SDK is async — the bridge is undesigned (and the SDK call shape in §7 is likely wrong)
- **Pass**: Pass 3 (Interface Contract Validation)
- **What**: §3 defines all four ports as synchronous `def`. The `claude_agent_sdk` Python API is async (`query()` is an async generator; `ClaudeSDKClient` is used via `async with`), and tool scoping is passed via `ClaudeAgentOptions(allowed_tools=...)`, not as a `query(prompt=..., allowed_tools=[])` kwarg as written in §7.2/§7.3/§12. The design neither acknowledges the sync/async boundary nor says how the adapter bridges it (e.g. `asyncio.run()`/`anyio.run()` per call), nor how streamed message chunks are collapsed into the single `str` result the ports promise.
- **Risk**: The illustrative adapter mechanics don't compile against the real SDK; the implementer must make an architectural call (async ports vs. per-call event loop) that the design was supposed to make. Per-call `asyncio.run()` also has latency cost — relevant to the very measurement M1 exists to take.
- **Fix**: Verify the SDK's actual call shape and document it in §7 (options object, async iteration, result-text extraction), and state explicitly that ports stay sync with the adapter bridging via `asyncio.run()` per call (or change the ports to async — but decide).

### [C8] task.md is empty — every file-level prescription in the design is untraced on the Task axis
- **Pass**: Pass 9 (Design-to-Task-to-AC Traceability)
- **What**: There is no "Files Changed" table, but §11 (File Layout) is a body-section prescription set: create `interfaces.py`, `loop.py`, `agent.py`, `persona/__init__.py`, `persona/persona.txt`, `providers/claude_adapter.py`, `observability/timing.py`, `interface/cli.py`, `tests/` (phase-port contract tests), `pyproject.toml`. `task.md` exists but contains zero tasks — all of these are untraced on the Task axis. The `/design` step is expected to produce task.md before dryrun runs. AC-axis status per prescription: `loop.py` (MPP-1 ✓), `persona/persona.txt` + `persona/` loader (MPP-6 ✓), `agent.py` (MPP-6 ✓), `interface/cli.py` (MPP-6/MPP-2 ✓), timing/DEBUG logging (MPP-5 ✓, though `observability/timing.py` is named only in design), `interfaces.py` (MPP-4 Tier-2 ✓ "clearly defined port interface"), `providers/claude_adapter.py` (MPP-1/MPP-4 Tier-2 ✓); **`tests/` contract tests and `pyproject.toml` have no AC on either axis** (invisible to the pipeline).
- **Risk**: Prescribed work silently drops — in particular the phase-port contract tests, which are the only stated verification vehicle for MPP-4's "confirmed by code inspection" claim.
- **Fix**: Populate `task.md` with actor/action/target tasks covering every §11 module (per the global task.md rules), and either add an AC (or design note) covering the contract-test deliverable and packaging, or explicitly descope them.

---

## Warnings (should fix, may cause issues)

### [W1] `observe()` docstring contradicts §7.4 and architecture.md on continue-vs-stop ownership
- **Pass**: Pass 3 / architecture consistency
- **What**: §3's `ObservePort` docstring says observe will "decide continue-vs-stop"; §7.4 says the opposite ("does NOT decide continue-vs-stop — that decision lives in the loop's intent switch"). architecture.md's Observer/Evaluator also owns "the loop's exit criterion". The design internally contradicts itself in the very contract text an implementer copies into `interfaces.py`.
- **Risk**: The docstring ships with a false contract; a future adapter author implements stop logic in observe() and gets silently ignored.
- **Suggestion**: Fix the §3 docstring to match §7.4, and note the deliberate M1 deviation from architecture.md's Observer role.

### [W2] Architecture.md's M1 table includes self-correction call-point wiring stubs; the design silently drops them
- **Pass**: Pass 1 (Completeness) / architecture consistency
- **What**: architecture.md's "M1 — Walking skeleton scope" table lists "Self-correction call-points: Wiring stubs only (no-op)". The design never mentions call-points (INJECT/GATE/RECORD/CAPTURE) — not even as named no-op seams in `loop.py`. The requirement's supersede note covers the orchestrator-is-the-loop decision, not this.
- **Risk**: Either the design is incomplete against the parent architecture's M1 scope, or the scope changed without being recorded — M8 will retrofit call-points into a loop that wasn't shaped for them.
- **Suggestion**: Either add the four named no-op call-points to §6, or add an explicit "call-point stubs deferred, supersedes architecture M1 table" line to §15.

### [W3] `perceive()`/`observe()` living inside the provider adapter undermines the MPP-4 drop-in story
- **Pass**: Pass 3 / architecture consistency
- **What**: architecture.md models context assembly (Perceiver) and state update (Observer) as **core** loop components; only the Agent port crosses to providers. The M1 design pushes all four phases — including provider-agnostic persona/context assembly and RunState bookkeeping — into `ClaudeAdapter`. A second adapter (vLLM) must duplicate perceive/observe logic verbatim.
- **Risk**: "Swapping the adapter swaps the provider" quietly becomes "swapping the adapter also swaps context assembly and state bookkeeping" — the seam M1 exists to prove is wider than the architecture intends, and copy-paste divergence between adapters starts at adapter #2.
- **Suggestion**: Acceptable for M1 if acknowledged — add a design note that perceive/observe are provider-independent and are expected to migrate to core (or a shared base) when adapter #2 arrives. The four-Protocol shape already permits this.

### [W4] DEBUG-log capture mechanism for sign-off is unspecified
- **Pass**: Pass 2 (Data Flow Trace)
- **What**: MPP-5 requires latency numbers "retrieved from DEBUG logs" at sign-off, and §10 forbids stdout. But nobody configures the logging system: root logger defaults to WARNING, so the `logger.debug(...)` line is dropped on the floor unless a handler+level is configured — and "never to stdout" rules out the obvious `basicConfig`. Where does the DEBUG record go (stderr handler? file?), and who configures it (`agent.py`? env var)?
- **Risk**: M1 ships, the log line never appears anywhere, and the milestone's key deliverable is unretrievable.
- **Suggestion**: Specify the handler policy (e.g. `agent.py` or the CLI configures a stderr or file handler at DEBUG for the `axiom` logger, opt-in via env var/flag) in §10.

### [W5] `allowed_tools` scoped list for `act()` has no source of truth
- **Pass**: Pass 3 (Interface Contract Validation)
- **What**: §7.3 says allowed_tools "is set to the permitted tool names for this run" — but never says which tools M1 permits, where the list lives (constant in `agent.py`? adapter default? per-run parameter?), or how it flows into `act()`. MPP-3's exemplar task ("List files in /tmp and summarise") implies at least a shell/file tool, unnamed.
- **Risk**: The sole M1 guardrail (per §7.3 and architecture.md's Guardrails GATE row) is configured by implementer improvisation — possibly overly broad, hollowing out the "pre-run scoping" promise.
- **Suggestion**: Name the M1 tool allowlist and its home (recommend: constant in `agent.py`, passed to `ClaudeAdapter.__init__()`).

### [W6] RunState mutability is ambiguous ("new (or mutated)") and `cycle_count` semantics skew the log
- **Pass**: Pass 4 (State Machine & Transitions)
- **What**: §5 says `observe()` returns "a new (or mutated) `RunState`" — two different contracts (value vs. reference semantics); Intent dataclasses are frozen but RunState is not, and no decision is recorded. Separately, `cycle_count` increments only in `observe()` (§7.4), which never runs on the short-circuit path — so the "Hello" DEBUG line reports "0 cycle(s), 1 spawn(s)", which readers of the MPP-5 data may misread.
- **Risk**: Aliasing bugs if callers hold references while observe mutates; sign-off latency table has confusing cycle numbers.
- **Suggestion**: Pick one (recommend: mutate-and-return, documented), and define cycle_count as "completed act cycles" explicitly in §5/§10.

---

## Observations (worth discussing)

### [O1] Fallback-RESPOND makes MPP-2's short-circuit measurement unfalsifiable as specified
Because parse failure also yields RESPOND (§7.2), a "1 spawn for Hello" observation can't distinguish genuine triage from a broken intent format. A distinct fallback marker (see C2) would also make the MPP-2 acceptance test honest.

### [O2] No test strategy for the phase-port contract tests
§11 shows `tests/` with "phase-port contract tests" but the design never says how ports are tested without live SDK spawns (each real call costs seconds and requires an authenticated CLI). A fake in-memory adapter would both enable fast tests **and** constitute the second-adapter existence proof MPP-4 wants "confirmed by code inspection" — worth one paragraph in the design.

### [O3] Unbounded `history` growth into the reason() prompt
§7.1 injects every prior act() result verbatim ("Step {n}: {result}") into each reason() prompt. A single large act() output (e.g. a long file listing) inflates every subsequent reason() call's tokens and latency — polluting exactly the per-cycle latency data M1 measures. Acceptable at MAX_CYCLES=10, but worth a stated truncation stance ("none, deliberately" is fine).

### [O4] Router stub naming mismatch with architecture.md
architecture.md M1 table says "Router: Minimal stub — one provider, wired in Python (`agent.py`)"; the design's §15 says Router is out of scope with wiring in `agent.py`. Functionally identical, but the traceability wording differs — a one-line note ("agent.py's fixed wiring IS the M1 Router stub") would close the loop.

---

## Pass 9 Note

No "Files Changed" table exists; body prescriptions from §11 were checked on both axes. `task.md` exists but is empty → all prescriptions untraced on the Task axis (consolidated as [C8]). `tests/` contract tests and `pyproject.toml` are additionally untraced on the AC axis.

---

## Summary

| Critical | Warnings | Observations |
|----------|----------|--------------|
| 8        | 6        | 4            |

**Verdict**: **FAIL — needs revision**

The core shape (four Protocols, split reason/act, composition root, import rules) is sound and well-argued. What blocks implementation is the contract layer: the intent wire format (C1), the parse-failure path (C2), the SDK failure/async reality (C3, C7), the loop's own API (C5), three of four loop exits (C6), and the spawn-count data flow (C4) all require implementer guesswork — plus an empty task.md (C8). Fixing C1–C8 is mostly specification, not redesign; a second dryrun should then pass.

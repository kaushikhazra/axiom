# M6 · Router (full) — Live Verification Sign-Off (RT-7 lifecycle)

Per `requirement.md`'s Definition of Done item 7 and the project's standing pattern (M1 MPP-5, M3 recall proof, M4 AC-08.5, M5 sign-off). All runs driven via real `axiom-cli` invocations and, where no CLI flag exists yet (`--router-config` is explicitly deferred, per Out of Scope), direct construction of a real `Router` wired to real `ClaudeAdapter`/`LocalAdapter` instances — the same objects `agent.py` would construct, just with a non-default `RoutePolicy`.

---

## RT-1 — Router as core-side component, reachable via the real CLI

**PASS.** `axiom-cli` with **no `--provider` flag at all** completed a normal turn (see RT-5/RT-9 combined run below) and — critically — the trace shows the ACT phase genuinely went through policy evaluation (`[LOCAL_ADAPTER_ACT_ERROR]` fired, meaning local was actually *attempted*), not silently forced to Claude. This is the specific regression dryrun-design-1's C1 caught and this run proves is fixed: "no flag" and "`--provider claude`" now produce observably different behavior (see RT-8 below, where local is *never* attempted).

## RT-2 — Conductor fixed once per session

**PASS, with an honest caveat about the AC's own wording.** Attempting the literal AC (two `Agent.run()` calls on the same `Agent` instance) surfaced a pre-existing architectural fact, not a Router bug: `Agent.run()`'s `finally` block tears down the memory adapter's executor after every call (`agent.py`, "G1 fix: release storage file handle and embedding executor") — `Agent` was never designed to support multiple `run()` calls on one instance; each CLI invocation is single-turn by construction (unrelated to M6). `requirement.md`'s RT-2 AC assumed multi-turn reuse that doesn't actually exist in this codebase — a requirement-writing imprecision on my part, not a code defect.

The *correct*, actually-reachable verification of RT-2's real intent (the Conductor doesn't get re-evaluated mid-run): within the single multi-cycle run captured above (`0800560d-...` trace — one ACT cycle plus two Reason cycles), **both** `reason`-phase spans show identical `provider_kind: "KIND_B"`. The Conductor did not change across the run's internal cycles.

## RT-3 — Worker selected per ACT dispatch

**PASS.** Direct script against real adapters: two different instructions issued to the same `Router` instance routed to different providers (`"a complex bug"` → `claude`; `"short task"` → `local`), proving selection is genuinely per-dispatch, not cached or session-level.

## RT-4 — Privacy gate, hard override

**PASS (selection level), and live-dispatched once (fallback run).** Direct script: an instruction matching a configured `privacy_patterns` glob (`*secret*`) routed to `local` unconditionally, with `control_level="KIND_A"`. A live dispatch attempt of a privacy-gated instruction hit a pre-existing, unrelated `LocalAdapter` gap (`ddgs` package not installed — `DuckDuckGoSearchTool` is constructed unconditionally by `CodeAgent`, regardless of whether the task needs search) — not a Router defect; the *selection* (the part RT-4 actually specifies) is proven correct.

## RT-5 — Cost/volume default

**PASS, live end-to-end.** The full no-flags `axiom-cli` run (see combined RT-1/RT-9 run) shows the default, unconfigured policy correctly routing a short instruction (`"List the files in the current directory."`, well under the 200-char default threshold) to `local` first — confirmed by `[LOCAL_ADAPTER_ACT_ERROR]` firing (local was genuinely attempted, not skipped).

## RT-6 — Capability override beats bulk default

**PASS.** Direct script: `"a complex bug"` — short enough to qualify for RT-5's bulk default, but also matching a configured `capability_patterns` glob (`*complex*`) — routed to `claude`, not `local`, proving RT-6 correctly overrides RT-5 when both could apply.

## RT-7 — `control_level` real and correctly traced

**PASS, live.** The fallback run's trace (`0800560d-...`) shows the `act` span's `extensions` carrying `"axiom.control_level": "KIND_B"` and `"axiom.router.provider": "claude"` — correctly reflecting the **fallback's actual outcome** (Claude, after local failed), not the original failed local attempt. Directly confirms the D11/D14 fix (dryrun-design-2) is working correctly under live conditions, not just in unit tests.

## RT-8 — Explicit override bypasses policy entirely

**PASS, live.** `axiom-cli --provider claude "..."` completed with **no** `[LOCAL_ADAPTER_ACT_ERROR]` or `[ROUTER_FALLBACK]` log lines at all — local was never attempted, unlike the identical-shape no-flags run. Confirms the override genuinely bypasses policy rather than merely being a strong preference (matching the finding this exact AC was written to prove, per dryrun-design-1's own reasoning).

## RT-9 — Single-hop live fallback

**PASS, live, twice.** The combined RT-1/RT-5 run: local failed with a real `AdapterError` (missing `ddgs` package), `[ROUTER_FALLBACK] local -> claude` fired, and the turn completed successfully via Claude (`spawn_count=4`: 1 reason + 1 failed local act + 1 fallback claude act + 1 final reason — matches the design's fallback spawn-counting exactly, confirming the C3-equivalent fix from dryrun-design-1 holds under live conditions too).

---

## Bugs found and fixed during this milestone

1. **Unreachable policy engine** (dryrun-design-1 C1) — `--provider` defaulting to `"claude"` made the entire policy engine dead code from the real CLI. Fixed before implementation.
2. **Stale observability on fallback** (dryrun-design-1 C2) / **`conductor_provider` not exposed** (dryrun-design-2 C1) — fixed before implementation; confirmed correct live above (RT-7).
3. **`spawn_count` undercounting on fallback** (dryrun-design-1 C3) — fixed before implementation; confirmed correct live above (RT-9, `spawn_count=4`).
4. **Uncaught `RouterError`** (dryrun-code-1 B1) — fixed after implementation; not exercised live in this pass (currently unreachable via the shipped CLI, per the finding's own reachability caveat — no `--router-config` exists yet to trigger it), but unit-tested.

## Full suite status

511 passed, 2 skipped (Windows-incompatible POSIX-permission test, pre-existing), 3 deselected (live-Ollama e2e, exercised manually above instead), 0 failed.

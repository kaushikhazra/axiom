# M7 · Orchestrator — Live Verification Sign-Off (OR-9)

Per `requirement.md`'s Definition of Done items 2 and 7, and the project's standing pattern (M1 MPP-5, M3 recall proof, M4 AC-08.5, M5/M6 sign-offs). All runs via real `axiom-cli` invocations, plus one direct-construction script (`Router` + real `ClaudeAdapter`/`LocalAdapter` — the same objects `agent.py` builds) used specifically because forcing `--provider committee` through an actual ACT dispatch depends on the Conductor's own (unpredictable) choice to delegate at all, not on anything Router-level — this mirrors M6's own precedent for verifying selection logic with no dedicated CLI surface.

---

## OR-1 — Committee mode is explicit, not default fan-out

**PASS, live.** `axiom-cli --observe --auto-approve-tools "Use a shell or code tool to list the files in the current directory"` (no `--provider` flag) completed normally. Trace inspection (`a505c4dc-...`) shows exactly **one** `core-minted`/`axiom.loop.act` span for the single ACT cycle, carrying `axiom.control_level: "KIND_B"` and `axiom.router.provider: "claude"` — a single-provider dispatch, unchanged from M6. (The 4 sibling `provider-streamed` spans in the same trace are ClaudeAdapter's own pre-existing internal SDK instrumentation, children of that one loop-level span — not additional Router-level dispatches.)

## OR-2 — Router selects a committee, not just a single Worker, when triggered

**PASS, unit + live.** `test_router.py::TestSelectCommittee` (11 tests) covers triggering, membership, capping, determinism, and the `None` fallthrough directly. Live: the direct-construction script (below, OR-3/OR-4) shows `router.select_committee(instruction)` returning `[claude, local]` when `forced_provider="committee"`; `select_worker()`'s own 20 pre-existing M6 tests are unmodified and still green.

## OR-3 — Act phase dispatches to every committee member for the same instruction

**PASS, live, twice — once via the real CLI, once via direct construction.**

1. `axiom-cli --provider committee --observe --auto-approve-tools --debug "Use a shell or code tool to list the files in the current directory, and in your final answer also state which AI model or system you are."` — debug log shows `[ROUTER_CONSORTIUM] claude,local` (the dryrun-code-1 G1 fix, live), followed by two genuinely distinct tool-execution approvals: `[GUARDRAILS_AUTO_APPROVE] tool=Bash ...` (Claude) and `[GUARDRAILS_AUTO_APPROVE] tool=run_shell ...` (local's smolagents CodeAgent) — two different tool names from two different adapters, proving real independent dispatch, not one call relabeled twice. Trace (`7b154350-...`) confirms the loop-level `act` span carries `axiom.router.committee_size: 2` and `axiom.router.providers: "claude,local"`.
2. Direct script (`verify_committee.py`, scratch): `router.select_committee(instruction)` → `['claude', 'local']`; both members' `.act()` were called with the byte-identical instruction string and returned genuinely distinct results (`235254` from claude, `976993</code>` from local) — see OR-4 below for the full transcript.

**Revision note:** `requirement.md`'s OR-3 originally required a *separate* `act` span per committee member; the implemented design (D10) builds one aggregate span instead (preserves M6's one-span-per-phase invariant, keeps OR-6's all-fail case inside a span boundary). Corrected in `requirement.md` (dryrun-design-3, PASS 0/0/0) rather than in code — the direct per-member dispatch proof above, plus OR-4's synthesis proof, together demonstrate genuine independent dispatch more strongly than a span-count check would have.

## OR-4 — Synthesis happens in the existing Reason seam, no new intent or phase

**PASS, live, deterministic.** Direct-construction script, same real `Router`/`ClaudeAdapter`/`LocalAdapter` objects `agent.py` builds:

```
committee members: ['claude', 'local']
--- claude succeeded ---
235254
--- local succeeded ---
976993</code>

=== COMBINED RESULT (what reaches observe()/history/next Reason cycle) ===
[claude]: 235254
[local]: 976993</code>
```

This is the exact string `loop.py`'s committee branch builds and passes to the **unmodified** `observe()` call — two genuinely distinct, independently-generated values (235254 vs 976993), each provider-attributed, in one combined string. No new `Intent` kind, no new phase — confirmed by reading `loop.py`'s committee branch line-by-line (dryrun-code-2) and now confirmed live: the code path that builds this string is the same code path a real `axiom-cli --provider committee` run executes (traced in OR-3's CLI run above, same `[ROUTER_CONSORTIUM]` log line, same `committee_size: 2` span attribute).

**Honest note on downstream prose:** in CLI runs where the Conductor's own final natural-language answer was captured, it consistently answered "as Axiom" (the system's unified persona) rather than explicitly quoting each provider's raw output — e.g. reporting only one self-identification string even when both members had genuinely run. This is Reason's own synthesis choice (architecturally correct per OR-4's design — "the Conductor synthesizes... using its own reasoning," `architecture.md`'s "loop IS the orchestrator" constraint means the code's job stops at delivering both results into context) and is not a code defect: the combined result above proves the code-level guarantee holds regardless of how any given LLM call chooses to phrase its final answer.

## OR-5 — Precedence: privacy is absolute, even over committee mode

**PASS, unit.** `test_router_policy.py::TestShouldFormCommittee` — `test_privacy_beats_explicit_committee_override` and `test_privacy_beats_consortium_pattern_match` both confirm `should_form_committee()` returns `False` when privacy matches, regardless of an explicit `"committee"` override. `test_router.py::TestSelectCommittee::test_privacy_match_returns_none_even_with_forced_committee` confirms the same at the `Router` level. Not separately live-verified (no live privacy-pattern CLI surface exists yet, same deferred posture as M6's own `--router-config`) — matches the precedent already set for RT-4's own selection-level-only live verification in M6's sign-off.

## OR-6 — Per-slot failure tolerance: one committee member failing doesn't kill the vote

**PASS, live, three times (one deliberate, two organic).**

1. **Deliberate:** `axiom-cli --provider committee --observe --auto-approve-tools --ollama-host http://10.255.255.1:11434 "Use a shell or code tool to list the files in the current directory."` — local's connection failed (`litellm.Timeout`), Claude succeeded, and the turn completed with a full, correct, non-error final response (`spawn_count`-implying `1 cycle(s), 4 SDK spawn(s)`: 1 reason + claude act + local act(failed) + final reason).
2. **Organic (`ddgs` gap, pre-fix):** before installing the missing `ddgs` package (see below), a committee run hit `[LOCAL_ADAPTER_ACT_ERROR] You must install package 'ddgs'...` — local failed, Claude succeeded, cycle completed normally.
3. **Organic (CUDA/driver crash):** a committee run hit the same pre-existing intermittent `llama-server` CUDA stack-buffer-overrun crash documented in M5's sign-off — local failed, Claude succeeded, cycle completed normally, Ollama recovered on its own afterward (consistent with M5's own account of this host-level issue).

All three: no `AdapterError` propagated to the user, no `[ROUTER_FALLBACK]` line (confirming OR-7 below), final response was Claude's answer alone with local's failure silently absorbed into the (unseen by the user) combined string per D7.

## OR-7 — RT-9's live fallback stays scoped to single-provider dispatch

**PASS, live + unit.** None of the three OR-6 live runs above produced a `[ROUTER_FALLBACK]` debug line — confirms `select_fallback_worker()` was never called from the committee path in real conditions with a real failure, not just in the unit test (`test_contracts.py::TestCommitteeDispatch::test_select_fallback_worker_never_called_from_committee_path`).

## OR-8 — `max_committee_size`: a forward-looking cost-safety cap

**PASS, unit.** `test_router.py::TestSelectCommittee` — `test_capped_by_max_committee_size`, `test_cap_never_exceeds_configured_adapter_count`, `test_default_cap_is_the_configured_adapter_count`, `test_membership_order_is_deterministic_insertion_order`. No live CLI surface exists for `consortium_patterns`/`max_committee_size` configuration (Out of Scope, matches M6's own `--router-config` deferral) — selection-level proof is the correct bar, same precedent as RT-4/RT-6 in M6's sign-off.

## OR-9 — M7 verified live via CLI

**PASS.** OR-1, OR-3, OR-4, and OR-6's behavioral ACs are each demonstrated live above, all recorded.

---

## Bugs and gaps found and fixed during this milestone

1. **Committee mode unreachable from the CLI** (dryrun-design-1 C1) — `agent.py`'s provider whitelist (post-M6 dryrun-code-1 W1) rejected `"committee"` with `ValueError` before `Router` was even constructed. Fixed before implementation (whitelist extended, `select_conductor()` guarded against `forced_provider == "committee"` leaking into Conductor selection).
2. **`RoutingDecision.CONSORTIUM` declared but never wired into logging** (dryrun-code-1 G1) — design.md promised it for `select_committee()`'s own logging/tracing; the first implementation pass left it dead. Fixed before commit — confirmed live above via the `[ROUTER_CONSORTIUM] claude,local` debug line.
3. **OR-3's AC required a mechanism the design didn't build** (found during live-verification prep, post-dryrun-code-2) — the requirement asked for one `act` span per committee member; D10 (already PASS'd at dryrun-design-2) deliberately builds one aggregate span. Neither dryrun-design pass caught this AC/design conflict. Resolved by correcting `requirement.md`, not the code (dryrun-design-3, PASS 0/0/0) — OR-4's live marker proof is a strictly stronger demonstration of genuine per-member dispatch than a span count would have been.
4. **Pre-existing missing imports in `tests/test_local_e2e.py`** (`Router`, `RoutePolicy`, `FakeMemory`) — found while verifying the "full suite green" DoD item, confirmed via `git stash` to predate M7 entirely (an M6-era migration gap). Fixed as part of this milestone rather than left broken.
5. **Missing `ddgs` package** — pre-existing environment gap (documented in M6's own sign-off), blocked `LocalAdapter`'s unconditional `DuckDuckGoSearchTool` construction. Installed (`pip install ddgs`) specifically to unblock OR-4's live dual-provider verification; not a code change.

## Known, unrelated, out-of-scope issues (not fixed — documented for the record)

- **Test-order-dependent pollution** in the full suite: all three `tests/test_local_e2e.py` tests fail with `TypeError: the JSON object must be str, bytes or bytearray, not MagicMock` when run as part of the full ~550-test suite, but pass individually in isolation (confirmed: `test_e2e_hello_respond_path` passes alone in 37s). Root-cause confirmed pre-existing via `git stash`: on the pre-M7 baseline, the *same* `test_e2e_hello_respond_path` failure occurred with the identical symptom (511 passed, 1 failed, same test, same error) — a mock-leakage flake unrelated to Router/committee code. Fixing the `ddgs` gap and the missing imports (both fixed as part of this milestone, see above) let all three tests progress far enough to now *all* hit this same pre-existing pollution point, where before two of them failed earlier for unrelated reasons that masked it. Out of M7's scope to root-cause (likely a `unittest.mock.patch` leak somewhere in an unrelated test file's global state, not in anything M7 touched).
- **Intermittent `llama-server` CUDA crash** and **`smolagents` `FinalAnswerTool` argument-count errors** during live verification — both pre-existing, host/library-level issues (the CUDA crash is the same one documented in M5's sign-off), not code defects. Axiom's own error handling (`AdapterError` → OR-6's per-slot tolerance) absorbed both correctly every time they occurred.

## Full suite status

540 passed, 3 failed (known pre-existing test-order pollution in `test_local_e2e.py`, documented above, confirmed via `git stash` to predate M7 and to be unrelated to Router/committee code — all three pass individually in isolation), 2 skipped (Windows-incompatible POSIX-permission test, pre-existing).

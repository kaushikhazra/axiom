# Code Dry-Run Report #4

**Scope**: `src/axiom/providers/claude_adapter.py` (reason() tool-less fix) + regression sweep of `loop.py`, `agent.py`, `interfaces.py`, `timing.py`, `interface/cli.py`
**Design**: `.claude/specs/002-m1-prao-proof/design.md` (§7 intro, §7.2, §7.3, §7.6, §4.1)
**Reviewed**: 2026-07-08
**Context**: dryrun-code-3 verdict was PASS-READY-FOR-E2E. Live E2E then revealed `reason()` was tool-less in name only — `allowed_tools=[]` is falsy, so `subprocess_cli.py` skipped `--allowedTools` entirely and the CLI ran with all built-in tools active (tool prompts bypassed the PRAO loop). Fix under review: `reason()` now uses `ClaudeAgentOptions(tools=[])`; the intent-format prompt was strengthened (ACT mandatory for tool/web/file/side-effect requests); design §7 intro + §7.2 updated. Live E2E subsequently PASSED both scenarios (Hello: 1 spawn / 0 cycles; web-search: 3 spawns / 1 cycle, correct answer).

---

## Test Verification

```
$ pytest tests/ -q
..........................                                               [100%]
26 passed in 0.39s
```

**26 passed** — exactly as expected. No regressions from the fix.

---

## Fix Confirmation (a)–(c)

### (a) reason()/act() split — intact and correctly scoped ✔

- `claude_adapter.py:159-161` — `reason()` builds `ClaudeAgentOptions(tools=[])`. **Verified against the installed SDK** (not just the docstring claim): `ClaudeAgentOptions` has both `tools` and `allowed_tools` dataclass fields; `subprocess_cli.py` guards `tools` with `if self._options.tools is not None:` and emits `--tools ""` for an empty list (genuinely tool-less spawn), while `allowed_tools` is guarded by truthiness (`if self._options.allowed_tools:`) — confirming why the old `allowed_tools=[]` silently left all CLI defaults active. The fix uses the only clean SDK mechanism for a tool-less spawn.
- `claude_adapter.py:203` — `act()` still builds `ClaudeAgentOptions(allowed_tools=self._allowed_tools)`, fed from `M1_ALLOWED_TOOLS = ["Bash", "WebSearch"]` in `agent.py:23` via the constructor (`agent.py` → `ClaudeAdapter(persona=..., allowed_tools=M1_ALLOWED_TOOLS)`). The truthiness guard is harmless here because the list is non-empty. Single source of truth preserved (§7.3/W5).
- The retry path in `reason()` (`claude_adapter.py:178`) reuses the **same** `options` object — the retry spawn is also tool-less. Correct.
- The reason/act fusion seam (§8) is now *actually* split at the subprocess level, which is what the E2E previously disproved and now confirms.

### (b) Strengthened intent prompt — coherent, wire format unchanged ✔

- `_INTENT_FORMAT_INSTRUCTIONS` (`claude_adapter.py:52-73`): the envelope spec is byte-identical in structure to §4.1 — same three shapes (`{"intent": "RESPOND", "text": ...}`, `{"intent": "ACT", "instruction": ...}`, `{"intent": "FINISH"}`), same single-line/no-markdown/no-fences constraints, same case-sensitivity rule. Only the *guidance* text under RESPOND/ACT was strengthened (RESPOND restricted to context/general-knowledge answers; ACT made mandatory for web search, real-time data, file access, commands, side effects; "you have zero tools" grounding).
- `_parse_intent()` (`claude_adapter.py:266-301`) is untouched and implements the §4.1 parse rules exactly (strip → `json.loads` → dict check → intent-value check → per-intent field validation). The prompt change is upstream of parsing and cannot alter parse behavior. Parse-failure retry and `[FALLBACK_RESPOND]` fallback paths unchanged.
- The strengthened text is internally consistent — no rule contradicts another; FINISH semantics unchanged.

### (c) Design consistency ✔ (with residue — see W1/S1/S2)

- §7.2 step 2 now shows `ClaudeAgentOptions(tools=[])  # truly tool-less: sends --tools "" to CLI` plus the "Why `tools=[]` not `allowed_tools=[]`" explanation (truthiness guard vs None-check). The explanation matches the installed SDK source verbatim-in-substance. **No remaining §7.2 claim of `allowed_tools=[]`.** ✔
- Module docstring (`claude_adapter.py:11-15`) records the finding under OQ-2 — accurate. ✔
- §7 intro (design.md:289) correctly scopes `allowed_tools` to `act()` only. ✔
- §7.6 error table matches `_run_query()` (`claude_adapter.py:220-258`) exactly: all six SDK exception rows, `is_error` handling in `_collect_query_result` (`claude_adapter.py:98-105`), catch-all with `AdapterError` pass-through, `BaseException` untouched. ✔
- §7.3, §7.5 (async bridge, timeout, generator cleanup), §4.1 parse rules, §5/§6 loop contracts — all still match the code. ✔

### Regression sweep of interacting modules ✔

- `loop.py`: imports `axiom.interfaces` only (seam intact); spawn_count incremented before each dispatch; RESPOND/FINISH/ACT switch and MaxCycles check unchanged; defensive `TypeError` on unexpected intent type. Untouched by the fix, no interaction.
- `agent.py`: wiring unchanged; `M1_ALLOWED_TOOLS` flows only into `act()`'s path. No interaction.
- `timing.py`, `cli.py`, `interfaces.py`: unchanged, no interaction with the fix.
- Grep for `tools=[]` / `allowed_tools=[]` across the repo: **no stale references remain in any `src/` or `tests/` code**. Remaining hits are documentation-only (see below).

---

## Bugs (will cause incorrect behavior)

*None.*

---

## Gaps (missing implementation)

*None.*

---

## Warnings (potential issues)

### [W1] design.md §4.1 "verbatim" instruction block is stale vs the strengthened code prompt
- **File**: `.claude/specs/002-m1-prao-proof/design.md:116-135`
- **Pass**: Pass 1 (Design Conformance)
- **What**: §4.1 states the model instruction text is "injected verbatim into the reason prompt" and shows the OLD wording ("Use it for direct answers and triage" / "Use it when a tool action is needed"). The code's `_INTENT_FORMAT_INSTRUCTIONS` now carries the strengthened RESPOND/ACT rules. The envelope, shapes, and parse rules are identical — only the guidance sentences diverge — but the design explicitly claims verbatim injection, so the claim is now false.
- **Risk**: Doc-only; zero runtime impact. Becomes a problem when someone re-derives the prompt from §4.1 (e.g. adapter #2) and silently reintroduces the weak triage rules the E2E proved insufficient.

---

## Style (code quality, conventions)

### [S1] §12 system diagram still shows `allowed_tools=[]` for the reason() spawn
- **File**: `.claude/specs/002-m1-prao-proof/design.md:672` and `:698`
- **What**: The diagram's `reason()` box and the `claude_agent_sdk.query()` box still read `ClaudeAgentOptions(allowed_tools=[])` — the exact stale claim the fix removed from §7.2. (Line 617's `M1_ALLOWED_TOOLS = ["Bash"]` staleness is pre-existing, noted in earlier iterations.)

### [S2] task.md checklist line describes the superseded implementation
- **File**: `.claude/specs/002-m1-prao-proof/task.md:51`
- **What**: The completed reason() task still says `_run_query(context, ClaudeAgentOptions(allowed_tools=[]))`. As a historical record of what was checked off it is defensible, but it now describes code that no longer exists and the wrong mechanism.

*(Both are documentation residue of the fix — the "consistency sweep" for `allowed_tools=[]` covered code and §7 but not the diagram/task references. No code change required.)*

---

## Summary

| Bugs | Gaps | Warnings | Style |
|------|------|----------|-------|
| 0 | 0 | 1 | 2 |

**Verdict**: **PASS WITH WARNINGS (documentation-only)**

The **code is clean**: `reason()` is genuinely tool-less (`tools=[]`, verified against the installed SDK's `subprocess_cli.py` flag handling), `act()` retains its correctly scoped `allowed_tools=["Bash","WebSearch"]`, the strengthened prompt preserves the §4.1 wire format and parse behavior exactly, the fix introduced no regressions in any interacting module, all 26 unit tests pass, and the live E2E passed both acceptance scenarios (Hello: 1 spawn / 0 cycles; web-search: 3 spawns / 1 cycle, correct answer).

**M1 is functionally complete.** The three findings (W1, S1, S2) are stale documentation references to the superseded `allowed_tools=[]` mechanism — a ~4-line doc sweep (design.md §4.1 block, §12 diagram ×2, task.md:51), zero code impact. Full **PASS — M1 COMPLETE** can be declared the moment those doc lines are aligned; no further code review iteration is needed.

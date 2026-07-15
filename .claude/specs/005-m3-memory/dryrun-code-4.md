# Code Dry-Run Report #4 (Verification Pass)

**Scope**: Verification of B1 and B2 fixes from dryrun-code-3.md. Files: `src/axiom/loop.py`, `src/axiom/agent.py`, `src/axiom/interface/cli.py`, `src/axiom/providers/base.py`, `src/axiom/interfaces.py`
**Design**: `.claude/specs/005-m3-memory/design.md`
**Reviewed**: 2026-07-15
**Methodology**: e-spec@apex-tools 1.2.0 (Pass 10: Value-Path Trace — verification mode)
**Prior report**: `dryrun-code-3.md` — verdict FAIL, two blocking bugs (B1, B2)

---

## Finding 2 (B1) — assembled_context computed then dropped: **CLOSED**

### Pass 10 Value-Path Trace

**Value**: `AssembledContext` (two-tier memory: `working_context` + `cognitive_memories`)
**Entry**: `PraoLoop._run_async()` → perceive → reason

**Step 1 — Value computed:**
`loop.py:155`: `assembled_context = await self._memory.assemble_context(user_input)` — unchanged from dryrun-3, correctly produces the two-tier context. ✔

**Step 2 — Value wired into transport:**
`loop.py:160`: `run_state.memory_context = assembled_context` — **NEW (B1 fix)**. The `AssembledContext` is now stored on `RunState.memory_context`.

`interfaces.py:78-79`: `memory_context: object = None` — field exists on the dataclass, typed as `object` to avoid circular import. Documented as duck-typed via `.cognitive_memories` and `.working_context` attributes (`interfaces.py:68-69`). ✔

**Step 3 — Value rendered into prompt (the critical link):**
`base.py:232`: `ctx = run_state.memory_context` — perceive() reads it.
`base.py:233`: `if ctx is not None:` — guards against the initial-construction None default. Since `loop.py:160` sets it before the while-loop and the `perceive()` call at `loop.py:165`, ctx is always the `AssembledContext` object on the first and every subsequent cycle. ✔

Cognitive tier rendering (`base.py:237-243`):
```python
if cognitive:
    lines = []
    for m in cognitive:
        mem_type = getattr(m, "memory_type", "memory")
        content = getattr(m, "content", str(m))
        lines.append(f"  [{mem_type}] {content}")
    sections.append("[ADDITIONAL CONTEXT FROM MEMORY]\n" + "\n".join(lines))
```

Working tier rendering (`base.py:245-251`):
```python
if working:
    conv_lines = []
    for unit in working:
        u_text = getattr(unit, "user_text", "")
        a_text = getattr(unit, "agent_text", "")
        conv_lines.append(f"  User: {u_text}\n  Agent: {a_text}")
    sections.append("[PREVIOUS CONVERSATIONS]\n" + "\n\n".join(conv_lines))
```

Both are appended to `sections`, which is joined at `base.py:269`: `return "\n\n".join(sections)`. This returned string becomes `context` at `loop.py:165` and is passed to `self._reason.reason(context)` at `loop.py:169`. ✔

**Step 4 — Value reaches the model:**
`context` (the prompt string) is the input to `reason()`, which sends it to the LLM. The cognitive memories appear under `[ADDITIONAL CONTEXT FROM MEMORY]` and working context under `[PREVIOUS CONVERSATIONS]` — both before `[CURRENT REQUEST]` and `INTENT_FORMAT_INSTRUCTIONS`. The model sees both tiers. ✔

**Verdict on B1**: **CLOSED.** The full chain is: `assemble_context()` → `run_state.memory_context` → `perceive()` reads it → renders into `sections` → joined into prompt string → `reason()` → model. No dropped value.

---

## Finding 1 (B2) — memory off-by-default + unreachable: **CLOSED**

### Evidence

**1. No `memory: bool` parameter anywhere:**
`grep -rn "memory: bool\|if self._memory is not None\|_memory_adapter = None\|memory=False\|memory=True" src/axiom/` → **no matches**. ✔

**2. Agent.__init__ constructs memory unconditionally:**
`agent.py:109-113`:
```python
from axiom.memory.adapter import CognitiveMemoryAdapter
from axiom.memory.config import MemoryConfig

_mem_cfg = memory_config if memory_config is not None else MemoryConfig()
self._memory_adapter = CognitiveMemoryAdapter(_mem_cfg)
```
No `if`/`else`, no toggle. `_memory_adapter` is always a live `CognitiveMemoryAdapter`. ✔

**3. PraoLoop.__init__ requires memory (non-optional):**
`loop.py:83`: `memory: MemoryPort` — positional-style parameter, no default value. Any caller that omits it gets a TypeError. ✔

**4. PraoLoop wires memory to the loop:**
`agent.py:115-122`: `PraoLoop(perceive=adapter, ..., memory=self._memory_adapter)` — always passes the live adapter. ✔

**5. Loop uses memory without guards:**
- `loop.py:155`: `await self._memory.assemble_context(user_input)` — no `if self._memory is not None`. Direct call. ✔
- `loop.py:179`: `await self._memory.append_unit(unit)` — no guard. ✔
- `loop.py:183-184`: `if recalled_ids: await self._memory.reinforce(recalled_ids)` — the `if` guards on empty list (correct), not on None adapter. ✔
- `loop.py:196`: `await self._memory.append_unit(unit)` — FinishIntent path, no guard. ✔

**6. CLI constructs Agent without any memory toggle:**
`cli.py:60`: `Agent(debug=args.debug, provider=args.provider, observe=args.observe)` — no `memory` param. `Agent.__init__` constructs memory unconditionally regardless. There is no `--memory` flag in argparse (correctly — none is needed when memory is constitutive). ✔

**7. Consolidation fires at session end:**
`agent.py:192`: `asyncio.run(self._memory_adapter.consolidate())` in the `finally` block. No None guard — memory_adapter is always present. ✔

**Verdict on B2**: **CLOSED.** Memory is constitutive by construction. No toggle, no None path, no guard. The CLI reaches the memory code path by default with zero user action required.

---

## New Issues Introduced by the Fix

### [W-NEW-1] memory_context field defaults to None — safe on all paths?

**File**: `interfaces.py:78-79`, `base.py:233`
**What**: `RunState.memory_context` defaults to `None`. `perceive()` guards with `if ctx is not None:` (`base.py:233`). Could any code path call `perceive()` before `loop.py:160` sets `memory_context`?
**Analysis**: `loop.py:155-160` sets `memory_context` BEFORE the `while True` loop. `perceive()` is only called at `loop.py:165`, inside the loop. The assignment is guaranteed to precede every `perceive()` call. Furthermore, the `if ctx is not None` guard means even a hypothetical direct-caller of `perceive()` with a raw `RunState` (e.g., in a unit test) gets a safe no-op rather than a crash. **Not a bug.**

### [W-NEW-2] Empty-memory case — does the prompt degrade gracefully?

**File**: `base.py:237, 245`
**What**: When memory is freshly initialised (no stored memories, no prior conversation), `assembled_context.cognitive_memories = []` and `assembled_context.working_context = []`. The guards `if cognitive:` and `if working:` both evaluate to `False` on empty lists. Neither `[ADDITIONAL CONTEXT FROM MEMORY]` nor `[PREVIOUS CONVERSATIONS]` sections appear in the prompt. The prompt degrades to the pre-M3 shape: `[PERSONA]` + `[CURRENT REQUEST]` + `INTENT_FORMAT_INSTRUCTIONS`. **Correct behavior — graceful degradation.** ✔

### [W-NEW-3] getattr fallback in perceive may mask future bugs

**File**: `base.py:240-241, 248-249`
**What**: `getattr(m, "memory_type", "memory")` and `getattr(m, "content", str(m))` use duck-typing with fallback defaults. If a future refactor renames `content` to `text` on `RecallResult`, the fallback silently renders `str(m)` (the repr) instead of raising. This is a conscious design trade-off (documented at `interfaces.py:68-69`: "duck-typed to avoid circular import"). Acceptable for M3.
**Severity**: Style/advisory — not a bug.

### Dryrun-3 Gaps and Warnings — status check

| ID | Status | Notes |
|----|--------|-------|
| G1 (no cognitive store writes at Observe) | **Unchanged** — acknowledged gap, agent-driven in M8 |
| G2 (FinishIntent doesn't reinforce) | **Unchanged** — FinishIntent path at `loop.py:188-198` still does not call `reinforce(recalled_ids)`. Design §13 does not carve out FinishIntent. Remains a gap. |
| W1 (reinforce awaited, not fire-and-forget) | **Unchanged** — deliberate B2 deviation, documented |
| W2 (sync storage on event loop) | **Unchanged** |
| W3 (spreading activation create_task teardown risk) | **Unchanged** |
| W4 (tests assert intermediate, not end behavior) | **Still relevant** — no new integration test verifying the full loop→perceive→reason chain with memory was observed in this file review scope |
| W5 (consolidate per-turn, not per-session) | **Unchanged** |

No new blocking bugs introduced by the fix.

---

## Summary

| Category | Count |
|----------|-------|
| B1 (Finding 2) | **CLOSED** |
| B2 (Finding 1) | **CLOSED** |
| New Bugs | 0 |
| New Warnings | 1 advisory (W-NEW-3, duck-typing fallback) |
| Prior Gaps/Warnings | Unchanged from dryrun-code-3 |

---

## VERDICT: **PASS**

Both blocking bugs from dryrun-code-3.md are confirmed CLOSED with file:line evidence:

- **B1 (value dropped)**: `loop.py:160` stores assembled context on `run_state.memory_context`; `base.py:232-251` reads it and renders cognitive memories as `[ADDITIONAL CONTEXT FROM MEMORY]` and working context as `[PREVIOUS CONVERSATIONS]` into the prompt string that `reason()` sends to the model. Full value chain verified.

- **B2 (memory unreachable)**: Zero matches for `memory: bool`, `if self._memory is not None`, `_memory_adapter = None`. `Agent.__init__` constructs `CognitiveMemoryAdapter` unconditionally (`agent.py:113`). `PraoLoop.__init__` requires `memory: MemoryPort` with no default (`loop.py:83`). CLI needs no flag — memory is constitutive by construction (`cli.py:60`).

No new blocking bugs introduced. Prior gaps (G1, G2) and warnings (W1–W5) from dryrun-code-3 remain unchanged — none are blocking for M3 acceptance.

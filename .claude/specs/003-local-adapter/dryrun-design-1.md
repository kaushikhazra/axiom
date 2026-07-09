# Dry-Run Design Review #1 — 003-local-adapter

**Reviewed:** 2026-07-09 (Velasari)
**Spec:** `003-local-adapter`
**Documents reviewed:** `requirement.md` (160 lines), `design.md` (833 lines)
**Reference context:** `002-m1-prao-proof/design.md`, `src/axiom/interfaces.py`, `src/axiom/loop.py`, `src/axiom/agent.py`, `src/axiom/providers/claude_adapter.py`, `tests/fake_adapter.py`, `tests/test_contracts.py`

---

## Verdict: FAIL

**1 Critical / 5 Warnings / 4 Observations**

Must resolve C1 before implementation. W1 and W5 require design-text corrections. W2–W4 require specification clarification.

---

## Critical Findings

### C1: Malformed tool arguments cause uncaught KeyError — agent crash

**Location:** design.md section 5.3, lines 438–453 (tool loop) + section 5.2.2, line 379 (tool registry lambda)

**Evidence:** When the model returns a tool_call with unparseable JSON arguments, the design catches `json.JSONDecodeError` and sets `fn_args = {}` (lines 441–446). The executor is then called with the empty dict. But the shell tool executor lambda is:

```python
lambda args: _execute_shell_tool(args["command"])
```

`args["command"]` on an empty dict raises `KeyError`. This exception is **not caught** anywhere in `_run_tool_loop()`. It propagates through `act()` → `PraoLoop.run()` → `timing.timed_run()` → `agent.py.run()`. In `agent.py`, only `MaxCyclesExceededError` and `AdapterError` are caught — a bare `KeyError` escapes to the CLI as an unhandled exception, crashing the agent.

**Requirement violated:** MLA-3 AC: *"Errors during tool execution (command fails, timeout) are caught and fed back to the model as error results."* Malformed arguments are a tool-execution error that is NOT fed back.

**Fix direction:** Either (a) wrap executor calls in try/except and feed errors back as tool-result strings (consistent with the design's own pattern for `_execute_shell_tool`), or (b) have the malformed-args branch skip execution entirely and feed an error string like `"[error]: could not parse tool arguments"` as the tool result.

---

## Warnings

### W1: cli.py marked [UNCHANGED] but design specifies adding --provider flag

**Location:** design.md section 8, file layout (line 582: `cli.py # [UNCHANGED]`) vs section 8.1 (line 628: *"CLI flag: cli.py gains a --provider flag"*)

**Evidence:** Section 8 file layout marks `cli.py` as `[UNCHANGED]`. Section 8.1 states `cli.py` gains a `--provider` flag passed to `Agent(provider=...)`. These are contradictory. If cli.py is truly unchanged, there is no way to select the local adapter from the CLI without editing code.

**Impact:** Implementer may either miss the CLI flag (if they follow the file layout) or modify cli.py when the layout says not to (confusion during task execution).

**Fix direction:** Mark `cli.py` as `[CHANGED]` in the file layout and add a one-line description of the delta.

---

### W2: google-adk is a declared dependency but never imported — dead dependency

**Location:** design.md section 9 (dependencies, line 636–638), section 10 (import boundary rules, line 669)

**Evidence:** The import boundary table for `providers/local_adapter.py` lists: `axiom.interfaces`, `axiom.providers.base`, `litellm`, `json`, `subprocess`, `logging`, stdlib. **No `google_adk` import.** The tool schema in section 5.2.1 is a plain dict in OpenAI function-calling format — no ADK `FunctionTool` class used. The model call uses `litellm.completion()` directly — no ADK `LiteLlm` wrapper used. Section 4.3 explicitly states: *"Decision: use litellm.completion() directly."*

Yet `google-adk` is listed as a core dependency in pyproject.toml (section 9, line 648). It would be installed but never imported by any M3 code. This is a dead dependency that adds install weight (~50+ transitive deps from google-adk) for zero functional use.

**Impact:** Bloated dependency tree. Potential version conflicts with google-adk's transitive dependencies. Misleading architecture signal (suggests ADK is integral when it is not used).

**Fix direction:** Either (a) remove google-adk from dependencies entirely (since direct litellm is the design decision), or (b) if ADK FunctionTool is actually intended for tool schema generation, add `google.adk` to the import boundary table and show the FunctionTool usage in the tool registry code.

---

### W3: Tool-loop exhaustion returns wrong "partial result" — reads last tool result, not model text

**Location:** design.md section 5.3, lines 468–475

**Evidence:** When `MAX_TOOL_ITERATIONS` is reached, the exhaustion handler attempts to extract partial text:

```python
last_content = messages[-1].get("content", "") if isinstance(messages[-1], dict) else ""
```

At loop exhaustion, the last messages appended are tool-result messages (`role: "tool"`). The assistant's message (with its text content, if any) was appended *before* the tool results. So `messages[-1]` is a tool-result dict, and `last_content` would be the raw tool execution output (e.g. a directory listing), not any model-generated summary.

**Impact:** The "partial result" returned to `observe()` on exhaustion is semantically wrong — it is a raw tool output, not a model response. The user sees a raw tool dump instead of the model's attempted summary.

**Fix direction:** On exhaustion, scan backward through `messages` for the last assistant-role message and extract its `content`, or synthesize a structured exhaustion message that includes both the iteration count and the last model text.

---

### W4: "~15 lines removed" claim understates the actual ClaudeAdapter diff

**Location:** design.md section 3.4, line 110

**Evidence:** The claim is *"~15 lines removed (perceive, observe, `_INTENT_FORMAT_INSTRUCTIONS`), ~3 lines added."* Actual line counts from `claude_adapter.py`:
- `perceive()` method: lines 150–165 = **16 lines**
- `observe()` method: lines 237–241 = **5 lines**
- `_INTENT_FORMAT_INSTRUCTIONS` constant: lines 52–92 = **41 lines**
- `_parse_intent()` function: lines 293–328 = **36 lines** (also moving to base.py per section 3.5)

Total removal: **~98 lines**, not ~15. The 3-line addition claim (import + inherit + super) is also low — reason() must change its `_parse_intent` reference from a local function to an import from `base.py`.

**Impact:** Misleads effort estimation and risk assessment. An implementer expecting a ~15-line diff may underestimate the refactoring scope.

**Fix direction:** Update the diff estimate to reflect the actual scope: ~98 lines removed (4 items), ~5–8 lines added (import, class declaration change, super().__init__, _parse_intent import).

---

### W5: Requirement MLA-1 AC specifies ADK LiteLlm wrapper but design bypasses it

**Location:** requirement.md line 38: *"LocalAdapter uses Google ADK with LiteLLM as the model backend: `LiteLlm(model="ollama_chat/qwen2.5:7b")`"* vs design.md section 4.3 line 252: *"Decision: use litellm.completion() directly"*

**Evidence:** The MLA-1 acceptance criterion explicitly names ADK's `LiteLlm` class as the model backend. The design explicitly rejects this in favor of direct `litellm.completion()` calls, relegating ADK to "schema conventions only" (and per W2, not even that). This is a deliberate design divergence from the requirement, but the requirement has not been updated to reflect the decision.

**Impact:** If the requirement is used for acceptance testing, the AC literally fails — the adapter does not use `LiteLlm(model=...)`. The design's rationale (section 4.3) is sound (direct control over tool loop), but the requirement should be aligned.

**Fix direction:** Update requirement.md MLA-1 AC to reflect the design decision: *"LocalAdapter uses LiteLLM (`litellm.completion()`) as the model backend, connecting to Ollama at `OLLAMA_API_BASE=http://localhost:11434`."* Remove or relegate the ADK LiteLlm reference.

---

## Observations

### O1: agent.py top-level LocalAdapter import forces litellm installation for Claude-only use

**Location:** design.md section 8.1, lines 604–605

**Evidence:** The design shows `from axiom.providers.local_adapter import LocalAdapter` as a top-level import in `agent.py`. Since `local_adapter.py` imports `litellm` at module level, **all** Axiom installations now require `litellm` as a dependency, even when only using ClaudeAdapter. Combined with W2's google-adk, this adds significant dependency weight for users who never use the local adapter.

**Mitigation (not required for M3):** Consider lazy imports (`if provider == "local": from ... import LocalAdapter`) or making litellm an optional dependency group (`pip install axiom[local]`). Acceptable for M3 dev-machine proof; revisit at M6 (router) when provider selection becomes a runtime concern.

---

### O2: _parse_intent enhanced pre-processing — OQ-3 is correctly identified

**Location:** design.md section 6 (parse rules) + OQ-3 (line 813)

**Evidence:** The enhanced `_parse_intent` (strip code fences, find first `{...}`) is additive: json.loads() is attempted first on the raw text. Pre-processing only fires on json.loads() failure. For ClaudeAdapter's clean JSON output, the happy path succeeds immediately — step 2 is never reached. No false-positive risk on the clean path. OQ-3 correctly identifies the need for a regression test (clean JSON through the enhanced parser). This is a sound design-time deferral.

---

### O3: OQ-1 and OQ-2 are genuinely deferrable with loud failure

**Location:** design.md section 14, OQ-1 (line 811) and OQ-2 (line 812)

**Evidence:**
- **OQ-1** (ADK LiteLlm vs direct litellm): Decision is already made (direct litellm). The OQ is a fallback note. Contained to `_query_model()` and `_run_tool_loop()`. Loud failure: if litellm.completion() doesn't work with Ollama, the first E2E test fails with AdapterError.
- **OQ-2** (qwen2.5:7b tool-calling reliability): Genuinely empirical. The design has fallback behavior (MAX_TOOL_ITERATIONS, error strings, fallback RESPOND). Loud failure: E2E tool test fails if the model can't produce tool calls.

Both are acceptable deferrals. No hidden design gaps.

---

### O4: message.model_dump() assumes Pydantic model on litellm response

**Location:** design.md section 5.3, line 436

**Evidence:** `messages.append(message.model_dump())` assumes the litellm response message object has a Pydantic `model_dump()` method. LiteLLM's `ModelResponse` and `Message` classes do use Pydantic, so this is expected to work. But the assumption is implicit — if a future LiteLLM version changes the response type, this would fail silently or raise `AttributeError`. Verify during implementation that `response.choices[0].message.model_dump()` produces a dict compatible with the messages list format expected by subsequent `litellm.completion()` calls.

---

## Port-Contract Integrity Check (Stress Area #1)

**Result: PASS.** The design keeps `loop.py` and `interfaces.py` completely untouched. No hidden requirement to change them was found:
- `PraoAdapterBase` lives in `providers/base.py`, within the adapter layer — not in core.
- `PraoAdapterBase` imports from `axiom.interfaces` (one-way dependency) — no circular import.
- The Protocol types are not modified; `PraoAdapterBase` satisfies them by duck typing.
- `PraoLoop` constructor accepts `LocalAdapter` identically to `ClaudeAdapter` via structural subtyping.
- The file layout explicitly marks both as `[UNCHANGED]`.

---

## W3 Shared Extraction Check (Stress Area #2)

**Result: PASS with caveats (W4).** The extraction is structurally sound:
- `perceive()` uses only `self._persona` and `RunState` — both available in the base class. Output is byte-identical for the same input.
- `observe()` uses no instance state — pure RunState mutation. Semantically identical.
- `_parse_intent()` is a pure function (no instance state) — safe to move to module level in base.py.
- `INTENT_FORMAT_INSTRUCTIONS` is a constant — safe to move.
- ClaudeAdapter's `reason()` and `act()` are untouched — they use `_run_query()` and Claude-specific SDK calls.
- `FakeAdapter` does NOT inherit from the base — no change required. Confirmed by reading `tests/fake_adapter.py`.
- `test_contracts.py` imports only `axiom.interfaces`, `axiom.loop`, and `tests.fake_adapter` — **zero ClaudeAdapter imports**. The "26 tests stay green" claim is confirmed: no test exercises ClaudeAdapter directly.

The diff-size claim (W4) is inaccurate but the behavioral-equivalence claim is valid.

---

## act() Tool-Execution Harness Check (Stress Area #3)

**Result: FAIL (C1, W3).** The harness design is mostly complete but has two specification gaps:
- **C1:** Malformed tool arguments → uncaught KeyError → agent crash. The JSONDecodeError catch sets `fn_args = {}`, but the executor lambda crashes on the empty dict.
- **W3:** Loop exhaustion returns wrong partial result (last tool result, not last model text).
- **Positive:** Termination on exhaustion correctly returns a string (not AdapterError). Tool execution errors in `_execute_shell_tool` are correctly caught and returned as strings. Unknown tools are handled. Multiple tool calls per turn are supported. Conversation history accumulates correctly within the loop.

---

## SDK Divergence Check (Stress Area #4)

**Result: WARNING (W2, W5).** The design is internally consistent in its use of direct litellm — the rationale is sound (full control over tool loop). But:
- The requirement AC explicitly names ADK's `LiteLlm` class — requirement-design misalignment (W5).
- google-adk is declared as a dependency but never imported — dead dependency (W2).
- ADK is described as used for "tool schema format" but the actual tool schema is a plain dict with no ADK imports.

The design should either align the requirement to match the decision, or actually use ADK for something.

---

## Intent Parse Robustness Check (Stress Area #5)

**Result: PASS.** The enhanced _parse_intent is additive and non-regressive:
- Happy path (clean JSON): json.loads() succeeds immediately. Pre-processing step is never reached.
- Weak-model path (JSON in code fences or wrapped in text): Pre-processing extracts the JSON substring. Correct and helpful for qwen2.5:7b.
- Composes correctly with M1's retry-once + [FALLBACK_RESPOND]: the retry path calls _parse_intent again, which uses the same enhanced parser. If both raw and retry fail extraction, fallback fires. No interaction bugs.
- OQ-3 correctly identifies the need to unit-test the clean-JSON path through the enhanced parser.

---

## Open Questions Check (Stress Area #6)

**Result: PASS.** Both OQ-1 and OQ-2 are genuinely deferrable with loud failure (see O3). No hidden design gaps:
- OQ-1 is already decided (direct litellm); the OQ is a fallback note.
- OQ-2 is empirical; no amount of design review can resolve it. The design has graceful degradation (MAX_TOOL_ITERATIONS, fallback RESPOND).
- OQ-3 (added in the design, not the requirement) is a sound verification step.

---

## Summary Table

| # | Severity | Finding | Location |
|---|----------|---------|----------|
| C1 | Critical | Malformed tool args → uncaught KeyError → agent crash | design.md §5.3 + §5.2.2 |
| W1 | Warning | cli.py marked [UNCHANGED] but design adds --provider flag | design.md §8 vs §8.1 |
| W2 | Warning | google-adk declared but never imported — dead dependency | design.md §9, §10 |
| W3 | Warning | Tool-loop exhaustion returns last tool result, not model text | design.md §5.3 |
| W4 | Warning | "~15 lines removed" understates actual ~98-line diff | design.md §3.4 |
| W5 | Warning | Requirement AC specifies ADK LiteLlm; design bypasses it | requirement.md MLA-1 vs design.md §4.3 |
| O1 | Observation | Top-level LocalAdapter import forces litellm for all installs | design.md §8.1 |
| O2 | Observation | OQ-3 (parse backward compat) correctly identified | design.md §14 |
| O3 | Observation | OQ-1 and OQ-2 genuinely deferrable with loud failure | design.md §14 |
| O4 | Observation | message.model_dump() assumes Pydantic — verify at impl time | design.md §5.3 |

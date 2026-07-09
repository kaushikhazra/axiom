# Dry-Run Design Review #2 — 003-local-adapter

**Reviewed:** 2026-07-09 (Velasari)
**Spec:** `003-local-adapter`
**Documents reviewed:** `requirement.md` (160 lines), `design.md` (867 lines)
**Prior review:** `dryrun-design-1.md` — 1 Critical / 5 Warnings / 4 Observations → FAIL
**Purpose:** Confirm every finding from iteration #1 is resolved and no new gaps introduced.

---

## Verdict: PASS

**0 Critical / 0 Warnings / 0 Observations**

All 10 findings from dryrun-design-1 are closed. No new contradictions, dangling references, or requirement-design drift detected. Design is **BUILD-READY**.

---

## Prior Finding Closure Verification

### C1: Malformed tool arguments cause uncaught KeyError — CLOSED

**Evidence:** design.md lines 443–461. The malformed-args branch (`json.JSONDecodeError`) now:
1. Does NOT call the executor — the `continue` on line 461 skips directly to the next tool_call.
2. Feeds `"[error]: could not parse tool arguments"` back as a tool-result message (lines 450–460).
3. Logs at WARNING level with the raw arguments for debugging (lines 452–455).

Additionally, lines 463–477 wrap every executor call in `try/except Exception`, converting any exception (including `KeyError` from missing dict keys) into an error string fed back as a tool result. The comment on lines 466–471 explicitly states: *"Any executor exception (KeyError, subprocess failure, timeout, etc.) is converted to an error string — never raised out of act()."*

**Path traced:** malformed JSON args → JSONDecodeError caught → error string as tool result → `continue` (executor never called). Even if the model somehow sends valid JSON missing `"command"`, the executor's `KeyError` is caught by the outer try/except. No exception escapes `_run_tool_loop()` or `act()` except `AdapterError` from the `litellm.completion()` call itself (lines 423–425), which is the correct contract.

**Verdict:** C1 is fully resolved. Both the malformed-args branch and the executor-error branch are hardened. MLA-3 AC ("errors during tool execution are caught and fed back to the model as error results") is satisfied.

---

### W1: cli.py marked [UNCHANGED] but design adds --provider flag — CLOSED

**Evidence:** design.md line 615: `cli.py # [CHANGED] -- gains --provider flag (claude|local) passed to Agent(provider=...)`. The file layout (section 8) now marks cli.py as `[CHANGED]` with a one-line description of the delta. Section 8.1 (line 663) elaborates: *"CLI flag: cli.py gains a --provider flag (claude or local) passed to Agent(provider=...). Default is claude — M1 behaviour preserved."*

**Verdict:** W1 is fully resolved. Layout and prose agree.

---

### W2: google-adk declared but never imported — dead dependency — CLOSED

**Evidence:** design.md section 9 (lines 667–689) lists dependencies: `claude-agent-sdk`, `anyio`, `litellm`. **No google-adk.** The pyproject.toml snippet (lines 676–683) confirms only three core deps. The import boundary table (section 10) has zero `google.adk` or `google_adk` entries. OQ-1 (line 844) explicitly states: *"Google ADK is removed from M3 dependencies entirely (see W2/W5 resolution)."*

Grep of design.md and requirement.md confirms every ADK reference is explicitly negative: "No Google ADK wrapper", "No ADK dependency", "ADK is not a dependency of this milestone". Zero positive/active ADK references remain.

**Verdict:** W2 is fully resolved. google-adk is removed from dependencies and prose.

---

### W3: Tool-loop exhaustion returns wrong "partial result" — CLOSED

**Evidence:** design.md lines 499–508. The exhaustion handler now:
1. Scans backward through `messages` for the last `assistant`-role message (lines 502–506).
2. Extracts its `content` text if non-empty.
3. If no assistant text found at all, returns an explicit exhaustion summary: `f"[tool loop exhausted after {self._max_tool_iterations} iterations]"` (line 508).

The comment on lines 499–501 explicitly addresses the original bug: *"At exhaustion, messages[-1] is a tool-result (role: 'tool'), NOT model text. We must find the last assistant-role message instead."*

**Verdict:** W3 is fully resolved. The last assistant text (or explicit exhaustion message) is returned — not a raw tool-result.

---

### W4: "~15 lines removed" claim understates actual ~98-line diff — CLOSED

**Evidence:** design.md line 110: *"~98 lines removed (perceive ~16 lines, observe ~5 lines, `_INTENT_FORMAT_INSTRUCTIONS` ~41 lines, `_parse_intent` ~36 lines), ~5–8 lines added (import base, class declaration change, super().__init__, _parse_intent import)."*

The breakdown matches the actual line counts from `claude_adapter.py` as measured in dryrun-design-1. The diff estimate is now accurate.

**Verdict:** W4 is fully resolved.

---

### W5: Requirement MLA-1 AC specifies ADK LiteLlm; design bypasses it — CLOSED

**Evidence:** requirement.md line 38 (MLA-1 AC): *"LocalAdapter uses LiteLLM directly as the model backend: `litellm.completion(model="ollama_chat/qwen2.5:7b")` against a local Ollama at `OLLAMA_API_BASE=http://localhost:11434`. No Google ADK dependency."*

This matches design.md section 4.3 (line 251): *"Decision: use litellm.completion() directly for both reason() and act(). Google ADK is not a dependency of this milestone."*

Requirement and design now agree: direct litellm, no ADK.

**Verdict:** W5 is fully resolved. Requirement-design alignment confirmed.

---

### O1: Top-level LocalAdapter import forces litellm for all installs — CLOSED (addressed)

**Evidence:** design.md lines 207–209: *"litellm is imported at construction or first use (deferred), not at module top-level, so that Claude-only installs do not pay the litellm import cost."* Section 8.1 (lines 639, 649): `agent.py` uses a lazy import inside the `provider=="local"` branch: `from axiom.providers.local_adapter import LocalAdapter  # lazy import`. Import boundary table (line 702) confirms: `litellm (deferred — imported at construction or first use, not at module top-level)`.

**Verdict:** O1 is addressed in the design. Both the adapter-level and agent.py-level imports are deferred/lazy.

---

### O2: OQ-3 (parse backward compat) correctly identified — CLOSED (accepted deferral)

**Evidence:** design.md OQ-3 (line 846): *"The JSON-extraction pre-processing (strip code fences, find first {...}) is additive, but verify it does not false-positive on ClaudeAdapter's clean JSON output. Add a unit test with clean JSON to confirm no regression."* Status: *"Verify during implementation of base.py."*

**Verdict:** O2 remains a correctly-scoped implementation-time verification. No design change needed.

---

### O3: OQ-1 and OQ-2 genuinely deferrable with loud failure — CLOSED (accepted deferral)

**Evidence:** OQ-1 is now RESOLVED (line 844) — the decision is final (direct litellm, ADK removed). OQ-2 (line 845) remains an empirical validation deferred to E2E. Both have loud failure modes.

**Verdict:** O3 is resolved (OQ-1 decided) or correctly deferred (OQ-2 empirical).

---

### O4: message.model_dump() assumes Pydantic — CLOSED (recorded for impl verification)

**Evidence:** design.md lines 435–440: The NOTE explicitly acknowledges the assumption and instructs implementers to verify at implementation time. *"Verify at implementation that response.choices[0].message.model_dump() produces a dict compatible with the messages list format expected by subsequent litellm.completion() calls. If the LiteLLM version changes the response type, this will fail loudly on the first live call."*

**Verdict:** O4 is recorded with a verify-at-impl note. No design change needed — loud failure on first live test.

---

## New-Issue Scan

Scanned for contradictions, dangling references, or drift introduced by the revision:

| Check | Result |
|-------|--------|
| ADK references (design.md + requirement.md) | All negative/exclusionary. Zero positive ADK usage. No dangling "use ADK for X" statements. |
| Dependency list vs import boundary table | Agree: `litellm` in both (deferred import). No unlisted deps. |
| File layout markers vs prose | All `[CHANGED]` / `[NEW]` / `[UNCHANGED]` markers match their prose descriptions. |
| Requirement ACs vs design sections | MLA-1 through MLA-6 all traceable (section 13). No AC references a feature the design doesn't specify. |
| Out-of-scope lists | requirement.md and design.md agree on what's excluded. ADK explicitly in both out-of-scope lists. |
| OQ status consistency | OQ-1 marked Resolved in design.md; requirement.md has no contradictory open question. OQ-2/OQ-3 status consistent. |
| Error contract | `AdapterError` is the only exception that escapes `act()` or `reason()` — consistent with MLA-1 AC and design section 4.5. Tool errors are strings, not exceptions. |
| Tool-loop exhaustion return type | Returns `str` (partial text or exhaustion message) — consistent with `act() -> str` signature and "not an AdapterError" decision (section 5.4). |

**No new findings.**

---

## Summary Table

| # | Severity | Finding | Status |
|---|----------|---------|--------|
| C1 | Critical | Malformed tool args → uncaught KeyError → agent crash | **CLOSED** — malformed-args branch skips executor + feeds error; executor wrapped in try/except |
| W1 | Warning | cli.py marked [UNCHANGED] but design adds --provider flag | **CLOSED** — marked [CHANGED] with delta description |
| W2 | Warning | google-adk declared but never imported — dead dependency | **CLOSED** — removed from dependencies and prose |
| W3 | Warning | Tool-loop exhaustion returns last tool result, not model text | **CLOSED** — scans backward for last assistant text |
| W4 | Warning | "~15 lines removed" understates actual ~98-line diff | **CLOSED** — corrected to ~98 lines |
| W5 | Warning | Requirement AC specifies ADK LiteLlm; design bypasses it | **CLOSED** — requirement updated to direct litellm |
| O1 | Observation | Top-level LocalAdapter import forces litellm for all installs | **CLOSED** — lazy/deferred import in both adapter and agent.py |
| O2 | Observation | OQ-3 (parse backward compat) correctly identified | **CLOSED** — accepted impl-time verification |
| O3 | Observation | OQ-1 and OQ-2 genuinely deferrable with loud failure | **CLOSED** — OQ-1 resolved; OQ-2 empirical deferral |
| O4 | Observation | message.model_dump() assumes Pydantic | **CLOSED** — recorded with verify-at-impl note |

---

**Final verdict: 0 Critical / 0 Warning / 0 Observation → PASS → BUILD-READY**

# Code Dry-Run Report #4

**Scope**: Phase 7–8 additions — `src/axiom/providers/claude_adapter.py` (KIND-B streaming spans + six helper functions + is_recording() gate) · `src/axiom/agent.py` (try/finally faculty shutdown + observe wiring) · `src/axiom/interface/cli.py` (--observe flag) · `tests/test_claude_adapter_spans.py` (27 tests)
**Design**: `.claude/specs/004-m2-observability/design.md` §3.2 / §3.6 / §4.3
**Reviewed**: 2026-07-13

> Prior iterations 1–3 reviewed the observability module (`observability/` + `loop.py`). All 0/0/0 PASS. This iteration reviews the NEW provider-side streaming-span code committed at 2ce9e5c.

---

## Bugs (will cause incorrect behavior)

### [B1] `_GEN_AI_SYSTEM = "claude"` — wrong `gen_ai.system` value; design and OTel spec require "anthropic"

- **File**: `src/axiom/providers/claude_adapter.py:73`
- **Pass**: Pass 1 (Design Conformance)
- **What**: The module constant is `_GEN_AI_SYSTEM: str = "claude"`. This value is stamped on every KIND-B child span's `gen_ai.system` attribute and flows through `schema.serialize_span_end()` into the JSONL record's `gen_ai_system` field.
- **Impact**: Design §3.2 states `gen_ai_system: str | null — Provider system name ("anthropic", "openai")` — "anthropic" is the explicit example for Anthropic's Claude. The OTel GenAI semantic conventions (v1.28.0, as pinned) define `gen_ai.system = "anthropic"` for the Anthropic provider. "claude" is a model-family name, not a provider-system name; it is not a valid OTel enum value for `gen_ai.system`. Every KIND-B `span_end` record in the trace file will carry `gen_ai_system: "claude"` instead of `"anthropic"`, silently misidentifying the provider for all downstream consumers that route or filter by `gen_ai_system`.
- **Fix**: Change the constant on line 73:
  ```python
  # Before
  _GEN_AI_SYSTEM: str = "claude"
  # After
  _GEN_AI_SYSTEM: str = "anthropic"
  ```

---

## Gaps (missing implementation)

_None._

---

## Warnings (potential issues)

### [W1] `Path` referenced in `agent.py` type annotations but never imported

- **File**: `src/axiom/agent.py:111,128`
- **Pass**: Pass 4 (Input Validation / Type Soundness)
- **What**: `self._trace_path: Path | None = None` (line 111) and `def trace_path(self) -> Path | None:` (line 128) both reference the name `Path`. There is no `from pathlib import Path` in the module's imports.
- **Risk**: `from __future__ import annotations` at line 11 makes all annotations strings (deferred evaluation), so the code does not crash at import time or at runtime. However: (1) `typing.get_type_hints(Agent)` raises `NameError: name 'Path' is not defined`; (2) mypy/pyright report `Name "Path" is not defined`; (3) any reflection-based framework (pytest-typed, pydantic v2 model resolution) that calls `get_type_hints()` on `Agent` will fail. The fix is a one-line import; the risk is low-probability but the defect is genuine.
- **Fix**: Add to `agent.py` imports:
  ```python
  from pathlib import Path
  ```

### [W2] `_open_child_span` docstring falsely claims "Returns a no-op span if tracer is None"

- **File**: `src/axiom/providers/claude_adapter.py:92–94`
- **Pass**: Pass 7 (Contract Violations)
- **What**: The function docstring says "Returns a no-op span if tracer is None (observability not wired)." The implementation body calls `tracer.start_span(name, attributes=attributes)` unconditionally — if `tracer` is `None`, this raises `AttributeError: 'NoneType' object has no attribute 'start_span'`. The function does NOT implement the promised no-op path.
- **Risk**: The real guard lives in `_collect_query_result` (line 145: `if tracer is not None and run_id is not None:`), so `_open_child_span` is never called with `None` in the current codebase. However, the docstring misdirects future maintainers: if someone removes or relaxes that guard relying on the documented no-op behaviour, they get a crash instead. The contract claim must match the implementation.
- **Fix**: Correct the docstring to reflect actual preconditions:
  ```python
  # Before (line 92-93):
  """Start and return an OTel span as a direct child of the current context.

  The caller is responsible for calling span.end() when the event is complete.
  Returns a no-op span if tracer is None (observability not wired).
  """

  # After:
  """Start and return an OTel span as a direct child of the current context.

  The caller is responsible for calling span.end() when the event is complete.
  Precondition: tracer must not be None. The guard 'if tracer is not None'
  in _collect_query_result ensures this is never violated at runtime.
  """
  ```

---

## Style (code quality, conventions)

### [S1] `test_no_spans_when_tracer_none_for_assistant_message` body is `pass` — verifies nothing

- **File**: `tests/test_claude_adapter_spans.py:489–511`
- **What**: The test is named to assert behavioural guarantees ("no spans when tracer is None for AssistantMessage") but its body is just `pass`. It always passes; it asserts nothing. Coverage tools report the test as "covered" but the documented contract — that `_handle_sdk_event_spans` with `tracer=None` and an `AssistantMessage` would crash (AttributeError), and that the guard in `_collect_query_result` is therefore load-bearing — is never verified.
- **Fix**: Replace the empty body with an assertion that makes the architecture contract machine-verifiable. The simplest meaningful assertion: call `_handle_sdk_event_spans` directly with `tracer=None` and an `AssistantMessage` and assert it raises `AttributeError`. This proves the `_collect_query_result` guard is non-optional:
  ```python
  def test_no_spans_when_tracer_none_for_assistant_message(self):
      """Calling _handle_sdk_event_spans(AssistantMessage, tracer=None) raises
      AttributeError — proof that the 'if tracer is not None' guard in
      _collect_query_result is load-bearing and must not be removed."""
      import pytest
      msg = _make_assistant_message()
      with pytest.raises(AttributeError):
          _handle_sdk_event_spans(msg, tracer=None, run_id="run-1", provider_kind="KIND_B", act_span=None)
  ```

---

## Summary

| Bugs | Gaps | Warnings | Style |
|------|------|----------|-------|
| 1 | 0 | 2 | 1 |

**Verdict**: FAIL — B1 causes incorrect `gen_ai_system` values in all KIND-B trace records; W1 and W2 are genuine maintenance risks; S1 provides false test-coverage confidence.

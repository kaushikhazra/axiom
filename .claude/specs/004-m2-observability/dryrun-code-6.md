# Code Dry-Run Report #6

**Scope**: `src/axiom/providers/local_adapter.py` (new `_enrich_current_span_gen_ai()` + call sites in `reason()` and `act()`) · `tests/test_local_adapter_spans.py` (17 new tests)
**Design**: `.claude/specs/004-m2-observability/design.md` §3.2 / §3.5 / §4.2 / §4.3
**Reviewed**: 2026-07-14

---

## Bugs (will cause incorrect behavior)

_None._

---

## Gaps (missing implementation)

_None._

---

## Warnings (potential issues)

_None._

---

## Style (code quality, conventions)

### [S1] Dead helper `_run_in_span` in `TestEnrichCurrentSpanGenAiAttrs` — never called, returns `None`, misleading docstring
- **File**: `tests/test_local_adapter_spans.py:115–127`
- **What**: `_run_in_span(self, adapter, tp, span_name)` is defined as an instance method on the class but is never called from any of the 7 tests in that class. The docstring claims it "returns the span_end record" yet the implementation returns `None` with a comment "caller extracts from sink". This is scaffolding that was not completed or removed. All 7 tests inline their own `tracer.start_as_current_span` context instead of using this helper.
- **Fix**: Delete lines 115–127 (the entire `_run_in_span` method). The method provides no value, its contract (return a `span_end` record) is unfulfilled, and its presence may mislead future test authors.

---

## Summary

| Bugs | Gaps | Warnings | Style |
|------|------|----------|-------|
| 0 | 0 | 0 | 1 |

**Verdict**: PASS WITH STYLE — no bugs, gaps, or warnings; one dead-code method to remove before the report is clean.

---

## Pass notes (all 9 passes executed)

**Pass 1 — Design Conformance:** ✓ All six OTel attribute keys set by `_enrich_current_span_gen_ai()` (`gen_ai.system`, `gen_ai.request.model`, `gen_ai.response.model`, `gen_ai.usage.input_tokens`, `gen_ai.usage.output_tokens`, `axiom.cost_usd`) match exactly the keys read by `schema.py:serialize_span_end()` (lines 143–151). `_GEN_AI_SYSTEM_LOCAL = "ollama"` is consistent with §3.5 commentary on provider naming. Both call sites (`reason()` line 161, `act()` line 250) are placed correctly after the model call completes. Enrichment of the current span (not child-span minting) is within scope of the task — §4.2 says KIND-A "can" produce child spans but does not mandate it; the task explicitly restricts to minimal enrichment only.

**Pass 2 — Execution Path Trace:** ✓ `trace.get_current_span()` returns the no-op INVALID span when no context is active; `is_recording()` on INVALID returns `False`; early return fires — zero overhead. When recording: four unconditional `set_attribute` calls, two conditional on non-None token counts. `getattr(self._model, attr, None)` is correct for the null-safe path; OTel SDK `set_attribute` accepts `int` natively for token counts.

**Pass 3 — Error Path Trace:** ✓ Outer `try/except Exception: pass` wraps the entire OTel block. `from opentelemetry import trace` inside the block means an import failure (e.g. OTel not installed) is also caught. In `act()`, if `agent.run()` raises before `_enrich_current_span_gen_ai()` is called, the span emits without gen_ai attrs (correct — no valid token data from a failed run). `except Exception as e` in `act()` then wraps and re-raises as `AdapterError` — `_enrich_current_span_gen_ai()` is never in that path.

**Pass 4 — Input Validation:** ✓ `_make_model_mock(input_tokens=None)` sets the attribute to `None`; `getattr(..., None)` returns `None`; `if input_tokens is not None` skips `set_attribute`; `attrs.get("gen_ai.usage.input_tokens")` returns `None` (key absent) → record field is `None`. `MagicMock(spec=[])` triggers `AttributeError` on attribute access which `getattr(..., None)` converts to `None`.

**Pass 5 — Resource Management:** ✓ `TracerProvider` instances in tests use only synchronous `SimpleSpanProcessor`-equivalent processors — no background threads, no resource leaks. No file handles opened.

**Pass 6 — Concurrency:** ✓ No shared mutable state. `_enrich_current_span_gen_ai()` reads `self._model_id` (immutable after `__init__`) and `self._model` (reassigned per-test but not during a span). OTel `set_attribute` is thread-safe per SDK contract.

**Pass 7 — Contract Violations:** ✓ Attribute key parity against `schema.py` verified line-by-line. ClaudeAdapter `is_recording()` gate pattern (claude_adapter.py:368–377) is faithfully mirrored — same lazy import, same early return, same exception swallow.

**Pass 8 — Code Quality:** ✓ `_GEN_AI_SYSTEM_LOCAL` module constant avoids magic string. Docstring accurately documents the attribute key→record field mapping. Module-level `sys.modules.setdefault` in the test file uses `setdefault` (not unconditional assignment) — test-isolation-safe if `test_local_adapter.py` runs first in the same process. 1 style finding (S1 above).

**Pass 9 — Security:** ✓ No user input reaches span attributes. `model_id` is set at construction. No secrets in span attributes.

# Code Dry-Run Report #8

**Scope**: `src/axiom/providers/local_adapter.py` (token-access fix: `_query_model()` returns `(text, input_tokens, output_tokens)`; `_enrich_current_span_gen_ai(input_tokens, output_tokens)` explicit params; `reason()` feeds real tokens; `act()` honest-null) · `tests/test_local_adapter_spans.py` (rewritten to real token_usage shape + fallback + contradiction: 22 tests)
**Design**: `.claude/specs/004-m2-observability/design.md` §3.2 / §3.5 / §4.2 / §4.3
**Reviewed**: 2026-07-14

> Re-review after dryrun-code-7 (0/0/0 PASS on 17 tests). Token-access fix adds `_query_model()` 3-tuple return, primary/fallback token extraction, and 5 new tests covering the extraction chain, fallback path, and contradiction proof.

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

_None._

---

## Summary

| Bugs | Gaps | Warnings | Style |
|------|------|----------|-------|
| 0 | 0 | 0 | 0 |

**Verdict**: PASS — all 9 review passes clean; 22/22 target tests passed; full suite 230 passed, 4 skipped (pre-existing `test_local_e2e` Ollama-ordering guards and Windows file-permission skips — unrelated to M2 gen_ai enrichment).

### Evidence per Pass

**Pass 1 — Design Conformance**: `_enrich_current_span_gen_ai()` sets the six OTel attribute keys (`gen_ai.system`, `gen_ai.request.model`, `gen_ai.response.model`, `axiom.cost_usd`, `gen_ai.usage.input_tokens`, `gen_ai.usage.output_tokens`) confirmed against `schema.py` `serialize_span_end()` mappings. Null policy (skip `set_attribute` when value is `None`) matches §3.5 "null when not available." `reason()` feeds real tokens; `act()` honest-null — both match design §4.2/§4.3. No design elements missing; no undocumented behaviour.

**Pass 2 — Execution Path**: `reason()` → `_query_model()` → 3-tuple → `_enrich_current_span_gen_ai(input_tokens, output_tokens)` → `_parse_intent()` → return. Retry path unpacks `retry_text, _, _` (tokens discarded — enrichment already committed to span, correct). `_query_model()`: primary extraction via `getattr(response.token_usage, "input_tokens", None)`; partial fallback (`if input_tokens is None or output_tokens is None`) fills each slot independently via `getattr(raw.usage, "prompt_tokens", None)` / `completion_tokens`. Token 0 (valid) passes the `is not None` guard and is correctly set on the span. All branches reachable, none dead.

**Pass 3 — Error Paths**: `_query_model()` exception handler differentiated by type; raises `AdapterError` with context. `_enrich_current_span_gen_ai()` outer `try/except Exception: pass` swallows OTel failures without touching main path. `act()` wrapper covers CodeAgent construction and `.run()`.

**Pass 4 — Input Validation**: Partial-fallback logic correctly handles all four cases: (both from `token_usage`), (both from `raw.usage`), (mixed), (neither → `None, None`). No boundary violations.

**Passes 5–6 — Resources / Concurrency**: No file handles, no connections, no async paths in scope.

**Pass 7 — Contracts**: `_enrich_current_span_gen_ai(input_tokens: int | None = None, output_tokens: int | None = None)` signature matches both call sites (keyword args in `reason()`; no-arg in `act()`). 3-tuple unpack correct at both `_query_model()` call sites. OTel `set_attribute` receives `str` key + `int` value — valid SDK types.

**Pass 8 — Quality**: Docstrings accurate and reference probe evidence. `[TAG]` log convention consistent. Comments explain smolagents 1.26 behaviour and probe confirmation. No TODO/FIXME.

**Pass 9 — Security**: No user input reaches shell commands. No secrets in scope.

**Tests**: 22 tests covering: direct `_enrich_current_span_gen_ai()` attribute set (7), integration chain via `reason()` (3), `raw.usage` fallback (2), null-safety (5), `is_recording()` gate (3), exception safety (2). `_make_chat_message_mock()` mirrors real smolagents 1.26 `TokenUsage` shape proven by `probe_local_tokens.py`. `del msg.token_usage` on `MagicMock` correctly makes `getattr(response, "token_usage", None)` return `None`. `spec=["content"]` mock simulates absent-attribute case. Contradiction test proves ChatMessage is the sole token source. All 22 PASS.

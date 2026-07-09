# Code Dry-Run Report #3

**Scope**: `src/axiom/providers/base.py` (`_extract_json_from_text`), `tests/test_shared_base.py` (`test_multi_fence_extracts_first_parseable_json`); confirming scan of all M3 files
**Design**: `.claude/specs/003-local-adapter/design.md`
**Prior review**: `.claude/specs/003-local-adapter/dryrun-code-2.md`
**Reviewed**: 2026-07-09

**Purpose**: Confirming-clean gate — verify the single O1 observation from dryrun-code-2 (greedy regex multi-fence edge) is resolved, no new defects were introduced, and everything else remains clean.

**Pytest result**: `69 passed, 2 skipped in 3.54s`

**M1 frozen-file verification**: `git diff HEAD -- src/axiom/loop.py src/axiom/interfaces.py` produces zero output. Byte-identical to M1 state. Confirmed.

---

## O1 Resolution — Multi-Fence Regex Fix

### What changed

`_extract_json_from_text` in `base.py:81–121` was rewritten from a single `re.search` with greedy `.*` spanning the full text (which could span across multiple code fences) to a two-strategy approach:

1. **Strategy 1 (lines 99–106)**: `re.finditer(r"```(?:\w+)?\s*(.*?)\s*```", text, re.DOTALL)` — non-greedy `.*?` between fence markers isolates each code-fence block individually. Within each block, `re.search(r"\{.*\}", block, re.DOTALL)` uses greedy `.*` to capture the full nested JSON object. Each match is appended to a `candidates` list.
2. **Strategy 2 (lines 108–111)**: Bare `{…}` fallback — `re.search(r"\{.*\}", text, re.DOTALL)` on the full text (unchanged from before; greedy, handles unfenced JSON).
3. **Selection (lines 114–119)**: Iterates candidates in order, returns the first that `json.loads()` parses into a `dict`. Returns `None` if none parse.

### Trace: single-fence still works

Input: `` ```json\n{"intent": "RESPOND", "text": "Paris."}\n``` ``
- `finditer` matches one block. Block content: `{"intent": "RESPOND", "text": "Paris."}`.
- Greedy `\{.*\}` captures the whole object (no inner braces to over-match within this single object — and even with nested braces, greedy captures to the last `}`).
- `json.loads` succeeds → returned.
- **Test**: `test_extract_json_from_text_code_fence` (line 151) — passing. ✅

### Trace: multi-fence returns first parseable JSON dict

Input: `` ```text\nHere is the explanation.\n```\n```json\n{"intent": "RESPOND", "text": "Paris."}\n``` ``
- `finditer` matches TWO blocks:
  - Block 1: `Here is the explanation.` — `\{.*\}` finds no match → no candidate added.
  - Block 2: `{"intent": "RESPOND", "text": "Paris."}` — `\{.*\}` captures it → candidate added.
- Strategy 2 (bare `{…}`): greedy on full text also produces a candidate (same JSON).
- First candidate from Strategy 1 is the JSON object → `json.loads` succeeds → returned.
- **Test**: `test_multi_fence_extracts_first_parseable_json` (line 185) — passing. ✅

### Trace: nested JSON still works (no regression from non-greedy change)

Input: `` ```json\n{"a": {"b": 1}, "c": 2}\n``` ``
- `finditer` matches one block. Block content: `{"a": {"b": 1}, "c": 2}`.
- Greedy `\{.*\}` inside the block captures from first `{` to last `}` — the full nested object.
- `json.loads` succeeds with `{"a": {"b": 1}, "c": 2}`.
- **Test**: `test_code_fence_multiline_nested_json` (line 166) — passing. ✅

### Trace: bare-JSON fallback works

Input: `Here: {"a": 1} and more text`
- `finditer` finds no fence blocks → no Strategy 1 candidates.
- Strategy 2: `\{.*\}` matches `{"a": 1}` → candidate.
- `json.loads` succeeds → returned.
- **Test**: `test_extract_json_from_text_prose` (line 155) — passing. ✅

### Trace: no-JSON returns None

Input: `no braces here at all`
- `finditer` → no blocks. Strategy 2 → no brace match. No candidates. Returns `None`.
- **Test**: `test_extract_json_from_text_no_json` (line 162) — passing. ✅

**Verdict on O1**: Fully resolved. The non-greedy inter-fence pattern prevents multi-fence spanning; greedy intra-block `\{.*\}` preserves nested JSON capture. All five edge cases verified by tracing + test confirmation.

---

## Prior-Finding Status (from dryrun-code-2)

All findings from dryrun-code-2 remain in their resolved/accepted state. No code changes were made to any file other than `base.py:_extract_json_from_text` and `test_shared_base.py` (new test added). Specifically:

| Finding | Status | Evidence |
|---------|--------|----------|
| B1/W1 (regex greedy) | ✅ Fixed (dryrun-2) | Unchanged |
| W2 (unknown provider ValueError) | ✅ Fixed (dryrun-2) | Unchanged |
| W3 (empty string return) | ✅ Accepted (dryrun-2) | Unchanged |
| W4 (shell=True dev-scope) | ✅ Accepted (dryrun-2) | Unchanged |
| W5/O5 (exhaustion vs error) | ✅ Confirmed correct (dryrun-2) | Unchanged |
| W6 (litellm import error) | ✅ Fixed (dryrun-2) | Unchanged |
| G1–G5, O3 | ✅ All resolved (dryrun-2) | Unchanged |
| O1 (multi-fence greedy span) | ✅ Fixed (this iteration) | base.py:99–106 `finditer`; test line 185 |

---

## New-Defect Scan

### Pass 1: Could the non-greedy inter-fence `.*?` truncate a legitimate single-fence block?

No. Within a single `` ```...``` `` pair, `.*?` is non-greedy *between the fence delimiters*, meaning it captures the *minimum* text between opening and closing ` ``` `. For a single fence this is the entire block content — there is no shorter ` ``` ` to stop at. The greedy `\{.*\}` inside the block then captures the full JSON object. Traced and confirmed by `test_code_fence_multiline_nested_json`.

### Pass 2: Could Strategy 2 (bare `{…}`) produce a false positive that shadows a correct Strategy 1 result?

No. Strategy 1 candidates are added to the list *before* Strategy 2. The selection loop (lines 114–119) returns the *first* parseable dict. Strategy 1 (fence-isolated) candidates always precede the Strategy 2 (full-text greedy) candidate. If a fence block contains valid JSON, it wins.

### Pass 3: Import integrity — test_shared_base.py

Line 20: `_extract_json_from_text` is imported from `axiom.providers.base`. The function is defined at module scope in base.py (line 81). Clean import, no circular reference.

### Pass 4: Test count reconciliation

- dryrun-code-2: 68 passed, 2 skipped (70 collected).
- dryrun-code-3: 69 passed, 2 skipped (71 collected).
- Delta: +1 test — `test_multi_fence_extracts_first_parseable_json` in `test_shared_base.py:185`. Correct.

### Pass 5: All other files unchanged

- `local_adapter.py`: no diff from dryrun-code-2 state. All logic intact.
- `agent.py`: no diff.
- `cli.py`: no diff.
- `claude_adapter.py`: no diff.
- `test_local_adapter.py`, `test_local_e2e.py`, `test_contracts.py`, `fake_adapter.py`: no diff.
- `pyproject.toml`: no diff.

---

## Bugs (will cause incorrect behavior)

_(none)_

---

## Gaps (missing implementation)

_(none)_

---

## Warnings (potential issues)

_(none)_

---

## Observations

_(none — the prior O1 is fully resolved; no new observations)_

---

## Summary

| Bugs | Gaps | Warnings | Observations |
|------|------|----------|--------------|
| 0 | 0 | 0 | 0 |

**Verdict**: **PASS — 0/0/0/0 — E2E-READY**

All prior findings are resolved or accepted. The multi-fence fix is correct and introduces no regressions. The code is fully clean and ready for live E2E testing against Ollama.

**Pytest summary**: `69 passed, 2 skipped in 3.54s`

**M1 frozen files**: `loop.py`, `interfaces.py` — byte-identical (zero diff).

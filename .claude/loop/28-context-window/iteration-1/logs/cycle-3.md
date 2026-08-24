# Cycle 3 — 2026-08-24 12:47 IST

## Where the artifact stands

`src/axiom/__init__.py` unchanged. `tests/test_context_window.py` (new) closes the three remaining untested paths with forced failures, not handler inspection.

## AC 6 — memory query actually fails

```python
monkeypatch.setattr(psutil, "virtual_memory", broken_virtual_memory)  # raises OSError
```

`test_memory_query_failure_falls_back_to_model_max` — `psutil` genuinely raises, `available_memory()` catches it (already wrapped since cycle 2), and the program still starts, resolving to the model's own 32768 since that side still works: `context: 32768 tokens` in output, no crash.

## AC 9 — both queries fail together

`test_both_queries_failing_falls_back_to_ollama_default` — a client whose `.show()` raises `ollama.ResponseError`, *and* `psutil` raising, in the same run. Asserts `context: Ollama default` in the startup line and that `options=None` reaches `chat()` — nothing fabricated, `num_ctx` genuinely omitted rather than sent as `None` or some placeholder.

## AC 8 — re-queried per run, not cached

Two pieces of evidence, unit and live.

**Unit** (`test_context_length_is_requeried_per_run`, parametrized): two `axiom.main()` calls with different `model_info` show different context numbers. First attempt used real `psutil` and failed — not a code bug, a test bug: raising the model's reported max to 262144 while leaving this machine's real available memory unmocked meant `min()` correctly picked the (smaller) real memory-derived figure instead, so the test asserted the wrong thing. Fixed by mocking `psutil.virtual_memory` to a budget larger than either case, isolating what AC 8 actually claims — the model side re-resolves — from the (already covered) memory side.

**Live**, two real installed models, back to back:

```
$ uv run axiom --model qwen2.5:7b
axiom: qwen2.5:7b at http://localhost:11434 (context: 32768 tokens)

$ uv run axiom --model ornith:9b
axiom: ornith:9b at http://localhost:11434 (context: 43513 tokens)
```

`ornith:9b`'s own reported max is 262144 — much larger than qwen's. But its architecture (`qwen35`: 32 layers, `key_length=256`, vs qwen2.5's 28 layers, derived head_dim 128) costs roughly 128 KiB/token against qwen2.5's 56 KiB/token, so on this machine's currently-available memory, `ornith:9b`'s *memory*-safe budget (≈43.5k tokens) binds instead of its model max. Stronger evidence than a same-side comparison would have been: it shows the full `min()` recomputes fresh each run, both branches, not just whichever query happens to be more visible.

## Criteria

| AC | State | Evidence |
|---|---|---|
| 1–5, 7 | met | cycles 1–2 |
| 6 memory undeterminable → Ollama's default | **met — new** | forced `psutil` failure, test above |
| 8 restart re-runs both queries | **met — new** | unit + live, above |
| 9 both fail → still starts on Ollama's default | **met — new** | forced double failure, test above |

**9 of 9 met.**

## Movement

Three criteria closed, all by forcing the failure rather than trusting the shape of the `try`/`except` already written in cycle 2. One test bug found and fixed along the way — a good outcome of the same kind cycle 4 of #26 produced: the test that was wrong pointed at something true (this machine's real memory genuinely constrains a 262k-context model), not a code defect.

## Assumptions that changed

None.

## Goal check

**Met.** All 9 acceptance criteria in issue #28, each with evidence. No more cycles needed for this iteration.

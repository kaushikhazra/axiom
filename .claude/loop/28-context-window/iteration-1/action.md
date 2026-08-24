# Action

Three criteria left, all untested paths rather than unwritten code: AC 6 (memory undeterminable), AC 8 (restart re-queries), AC 9 (both fail together).

Force `available_memory()` to actually fail — monkeypatch `psutil.virtual_memory` to raise, confirm `available_memory()` returns `None` rather than propagating, and confirm the program still starts and shows "Ollama default" (or a memory-only-blind context, if the model side still resolves) rather than crashing. Do the same for the model side already covered by AC 5's transcript, but now force *both* to fail in the same run for AC 9 — confirm a single combined "Ollama default" run, not two separate near-misses.

For AC 8, produce two consecutive runs on this machine with different `--model` values whose max context differs (e.g. `qwen2.5:7b` vs `ornith:9b`, 32768 vs 262144) and show the startup line's context figure actually changes between them — proving the query re-runs rather than caching or hardcoding from the first run.

Prefer unit tests with a fake client/psutil over more scratch scripts where the previous cycles' pattern already fits — AC 6 and AC 9 are exactly the shape `tests/test_interrupt.py`'s `FakeClient` already handles (a fake that raises where the real thing would raise); extend it or add a sibling test module rather than another proxy.

When all 9 are met, this iteration is done — say so plainly in the log, push the branch, and prepare the same handoff shape #26 used (PR, evidence summary) rather than inventing a new one.

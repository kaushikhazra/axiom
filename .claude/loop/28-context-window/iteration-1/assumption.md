# Assumptions

Standing inputs. May change between iterations — when one does, say so in that cycle's Observe.

- Python 3.12+. Code lives in `C:/Projects/axiom/src/`. Dependencies managed with `uv`.
- **KISS, not asceticism.** Reach for a good library rather than writing it.
- The model's max context length comes from Ollama's own `show` API (`ollama.Client.show(model)` / `model_info`), via the already-installed `ollama` package. No new dependency for this half.
- Available-memory queries use `psutil`. Add it as a direct dependency.
- **Safe memory budget is locked: 70% of currently available (free) memory, not total installed.** Decided with Kaushik 2026-08-24, backed by general local-LLM sizing guidance (~30% headroom for OS/other apps). Not the loop's to re-derive.
- Where the model reports no max context, or available memory can't be determined, or both fail: use Ollama's own default (do not pass `num_ctx`, or pass none of the computed values) — never an axiom-invented constant.
- `pytest`, tests in `C:/Projects/axiom/tests/`.
- Loop engineering, not spec-driven. Do not write `requirement.md`, `design.md`, or `task.md`, and do not run the `/e-spec:*` or `/dryrun-*` skills.
- Read `C:/Projects/axiom/CLAUDE.md` before the first write.
- **Work happens on a feature branch, never `master`.** `protected_branch_guard.py` blocks editing any source or test file while `master` is checked out — not just pushing. Branch: `feature/28-context-window`.
- Commit each cycle's work. Plain pushes are allowed; force-pushes and tag pushes are blocked by a hook and must be left to Kaushik.
- This continues `src/axiom/__init__.py` from issue #26 (merged). Read it before writing — do not regenerate it.

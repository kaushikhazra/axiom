# Assumptions

Standing inputs. May change between iterations — when one does, say so in that cycle's Observe.

- Python 3.12+. Code lives in `C:/Projects/axiom/src/`. Dependencies managed with `uv`.
- **KISS, not asceticism.** Reach for a good library rather than writing it.
- This continues `src/axiom/__init__.py` from issues #26 and #28 (both merged). Read it before writing — do not regenerate it.
- The "effective context length" AC 1 triggers against is #28's already-computed value (`min(model_max_context, memory_safe_context)`), not a fresh figure.
- **The numbers in the issue are locked, not the loop's to re-derive:** 90% trigger threshold; kept-window ladder is 10 pairs -> 5 -> 2 -> 0 (everything). A "pair" is one `{user, assistant}` exchange — 2 entries in the `messages` list.
- Compaction needs a mechanism (most likely summarization via the model itself, using the already-configured Ollama client) and a way to measure current token usage against the effective context length. Neither is locked — this is genuine design surface for cycle 1 to work out and document, the way #28's cycle 1 worked out the KV-cache formula. Don't invent a number; discover it against the real client and record the evidence.
- `pytest`, tests in `C:/Projects/axiom/tests/`.
- Loop engineering, not spec-driven. Do not write `requirement.md`, `design.md`, or `task.md`, and do not run the `/e-spec:*` or `/dryrun-*` skills.
- Read `C:/Projects/axiom/CLAUDE.md` before the first write.
- **Work happens on a feature branch, never `master`.** `protected_branch_guard.py` blocks editing any source or test file while `master` is checked out. Branch: `feature/29-context-compaction`.
- Commit each cycle's work. Plain pushes are allowed; force-pushes and tag pushes are blocked by a hook and must be left to Kaushik.

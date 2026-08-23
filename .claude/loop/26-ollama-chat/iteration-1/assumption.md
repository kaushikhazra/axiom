# Assumptions

Standing inputs. May change between iterations — when one does, say so in that cycle's Observe.

- Python 3.12+. Code lives in `C:/Projects/axiom/src/`. Dependencies managed with `uv`.
- Use the official `ollama` Python package as the client. Do not hand-roll HTTP.
- **KISS, not asceticism.** Reach for a good library rather than writing it. "Minimal" here means no unearned structure — not zero dependencies.
- Default model `qwen2.5:7b`. Also installed locally: `qwen2.5-coder:7b`, `gemma4:e2b`, `ornith:9b`.
- Default host `http://localhost:11434`.
- `pytest`, tests in `C:/Projects/axiom/tests/`.
- Loop engineering, not spec-driven. Do not write `requirement.md`, `design.md`, or `task.md`, and do not run the `/e-spec:*` or `/dryrun-*` skills.
- Read `C:/Projects/axiom/CLAUDE.md` before the first write.
- Commit each cycle's work. Plain pushes to `master` are allowed; force-pushes and tag pushes are blocked by a hook and must be left to Kaushik.

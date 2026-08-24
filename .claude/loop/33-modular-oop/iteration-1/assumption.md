# Assumption

Standing inputs. These are given - do not re-derive them, and do not spend a cycle
deciding them.

- **Python best practices decide the shape.** No module split, class design, or naming
  scheme has been pre-chosen. Idiomatic modern Python for a program this size: standard
  library where it suffices, `dataclass` where a class is just data, `Protocol` or an
  abstract base only where something is genuinely substituted, type hints throughout,
  no getters and setters for their own sake.
- **Python 3.12, pytest, `uv`.** No new runtime dependencies beyond `ollama`, `httpx`
  and `psutil`.
- **`axiom:main` stays the packaging entry point** named in `pyproject.toml` (AC 3).
- **`src/` may not exceed 447 lines** - 298 baseline plus the 50% cap of AC 14.
- **Ollama runs at `localhost:11434`**, but the test suite must be green with it stopped.
- **The repo's own rules apply**: KISS over structure, one command per shell invocation
  (never sequence with `;`, `&&` or newlines), nothing committed under a `temp` name,
  and the loop's own files stay in this folder while the code stays in `src/` and `tests/`.
- **The branch is `feature/33-modular-oop`.** Commits reference #33.

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

## Settled in cycle 1 - do not rediscover

- **`AXIOM_DEBUG_MAX_CONTEXT=500` is exported in this session's environment**, left over
  from #29's live compaction runs. It is not in any settings file and not in the Windows
  User or Machine environment, so there is nothing persistent to remove, and a child
  process cannot unset it in its parent. It will be present for every command this
  session runs.
- **It no longer matters.** `tests/conftest.py` clears it for every test via an autouse
  fixture, so the suite is green with the variable set. Run `pytest` normally. If a
  future cycle sees six context/compaction tests fail together with a startup line
  reading `context: 500 tokens, debug override`, that fixture has been lost - restore
  it rather than working around it.
- **The measuring instrument is `tests/test_characterization.py`**, compared against
  `tests/baseline/transcript.txt`. AC 1 is settled by that comparison. The baseline is
  regenerated only with `AXIOM_WRITE_BASELINE=1`, and regenerating it to clear a failure
  is the one move that destroys its value.

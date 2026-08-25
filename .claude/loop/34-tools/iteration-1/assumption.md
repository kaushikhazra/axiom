# Assumption

Standing inputs. These are given - do not re-derive them, and do not spend a cycle deciding
them.

## The codebase this lands in

#33 merged (PR #36). `src/axiom/` is six modules: `config`, `context`, `compaction`,
`backend`, `terminal`, and `__init__` holding the chat loop and `main()`.

- **The seam is `backend.ModelBackend`** - `model_info`, `stream`, `complete`. Tool support
  extends it. `ollama` and `httpx` stay inside `backend.py`; nothing above it names a vendor
  type, and vendor errors are translated at that boundary into `BackendError` /
  `ConnectionLost`.
- **`main(argv, using=...)` takes a backend from its caller.** Tests inject; they do not
  patch module globals. Keep it that way - a tool test that reaches for `setattr` has taken
  a wrong turn.
- **`terminal.py` owns every `print` and `input`.** Tool visibility lines belong there, not
  in the tool code.
- **`tests/conftest.py`** holds `StubBackend`, `feed()`, `chunk()`, and the autouse fixture
  clearing `AXIOM_HOST` / `AXIOM_MODEL` / `AXIOM_DEBUG_MAX_CONTEXT`. Extend the stub for
  tools rather than writing a second one.

**#33's 447-line ceiling does not apply here.** It was a constraint on that refactor, to stop
a restructure from ballooning the code. #34 adds a feature and `src/` will grow. Keep it
KISS, but do not squeeze against a budget that is not yours.

## Models on this machine

| model | architecture | tools | notes |
|---|---|---|---|
| `qwen2.5:7b` | qwen2 | yes | 32k context |
| `qwen2.5-coder:7b` | qwen2 | yes | same family as above - does **not** count as a second family for AC 3 |
| `gemma4:e2b` | gemma4 | yes | 131k context, also a *thinking* model |
| `ornith:9b` | qwen35 | yes | 262k context, thinking, agentic system prompt |
| `gemma2:2b` | gemma2 | **no** | pulled and verified for AC 8: `ollama show` reports `completion` only, no `tools` capability |

**AC 3's three families are `qwen2.5:7b`, `gemma4:e2b`, `ornith:9b`.** Two of the three are
thinking models, which is exactly the variation AC 6 and AC 7 are aimed at.

16GB machine: models are 1.6-7.2GB and Ollama will swap between them. A cycle that exercises
all three spends real time on loading alone. Budget for it.

## Given

- **Python 3.12, pytest, `uv`.** New dependencies are allowed here if a good library exists -
  the repo rule is reuse before build - but say why in the log, and prefer the standard
  library for running a subprocess.
- **`axiom:main` stays the packaging entry point.**
- **Ollama's own tool API is the starting point**, not a hand-rolled prompt convention:
  `chat(..., tools=[...])` and `message.tool_calls`. Whether it holds across all three
  families is the first thing cycle 1 finds out, and AC 6 exists because it may not.
- **The safety rules in `CLAUDE.md` bind every cycle.** They are restated in `observe.md`.
- **The repo's own rules apply**: KISS over structure, one command per shell invocation,
  nothing committed under a `temp` name, loop files stay in this folder while code stays in
  `src/` and `tests/`.
- **The branch is `feature/34-tools`.** Commits reference #34.

# Assumption

Standing inputs. These are given - do not re-derive them, and do not spend a cycle deciding
them.

## The codebase this lands in

Row 9 (#48) merged in PR #50. **377 tests, green and hermetic** at scaffold time.

- **`models.py` exists and is this row's foundation.** `sorted_models()`, `read_choice()`,
  `write_choice()`, `unreadable()`, `choose()` and `picked()`. #49 AC 2 requires the switch
  list to match the startup list, so **call these rather than copying them** - a second
  sorting implementation is exactly how the two lists drift apart.
- **`backend.ModelBackend.installed()` raises rather than swallowing.** `ConnectionLost` on an
  unreachable host, `[]` for a reachable host with nothing on it. #49 AC 30 needs the first of
  those to be survivable rather than fatal, which is the opposite of #48 AC 31.
- **`terminal.py` owns every print and the only `input()`.** `show_models(models, host,
  default)`, `ask_model()`, `refuse_model(answer, count)`, `note_settled`,
  `note_model_missing`, `note_choice_forgotten`, `note_choice_unreadable`,
  `note_choice_saved`, `report_no_host`, `report_no_models` all exist.
- **`__init__._settle_model()` runs before anything else starts**, and `_remember()` writes the
  choice. `/model` is the same decision made again mid-run, and should reuse both.
- **`EXIT_COMMANDS = {"/exit", "/quit"}` is the only command handling there is.** No `/help`,
  no command dispatch, no argument parsing at the prompt. `/model` is the third command and
  the first that is not an exit - and the first that takes an argument.
- **`CANNOT_START = 2`** is the only non-zero exit. #49 adds none: every criterion here either
  carries on or leaves with 0.
- **The chat loop holds `messages`, `model`, `capable`, `declarations`, `callable_names`,
  `effective_context` and `chat_options` as locals in `_chat`.** A switch changes `model`,
  `capable`, `declarations`, `callable_names`, `effective_context` and `chat_options`, and
  must leave `messages`, `limits`, `attached` and `instructions` alone. **That list is most of
  AC 10 to AC 17** and is worth writing out before touching the loop.
- **`compaction.maybe_compact` and `compaction.too_large` already run per turn** against
  `effective_context`. AC 18 and AC 19 are largely about letting the existing machinery see the
  new window rather than writing new machinery.
- **`tests/conftest.py`'s `StubBackend` records `asked_about`** - every model name it was asked
  anything about, in order. Added by #48 cycle 3 because AC 29 had no real test without it.
  AC 15 and AC 16 here are the same class of claim; use it.
- **`StubBackend(models=[...], listing=exc)`** controls the host's answer and its failure.
- **`tests/test_characterization.py`'s `StubClient` has `list()`** returning entries exposing
  `model` and not `name` - it is the vendor-shaped stub, separate from `StubBackend`.
- **`conftest.isolate_remembered_choice` is autouse** and points
  `models.DEFAULT_CHOICE_FILE` at `tmp_path` for every test. A test that is *about*
  remembering points at its own file explicitly.

## The Ollama API, measured 2026-08-27

Do not re-research this.

- `Client.list()` returns `ListResponse`; entries expose **`.model`, never `.name`**, and carry
  no `capabilities`. Tool support comes from `show()`, which `supports_tools` already uses.
- **The order is `modified_at` descending** - not sorted, and it moves when anything is pulled.
- **Ollama has no concept of a default model.**

## The local Ollama, and what testing may use it for

`http://localhost:11434`, five models:

| model | parameter size | tools |
|---|---|---|
| `gemma2:2b` | 2.6B | **no** |
| `gemma4:e2b` | 5.1B | yes |
| `ornith:9b` | 9.0B | yes |
| `qwen2.5:7b` | 7.6B | yes |
| `qwen2.5-coder:7b` | 7.6B | yes |

**Kaushik has asked that development and hands-on testing use this local Ollama.** It does not
loosen the hermeticity rule: every criterion is settled against a stub.

`gemma2:2b` is the only model with no tool support, which makes **switching to and from it**
the live instrument for AC 11 and AC 16 - the two hardest criteria in this row.

## Given

- **`requires-python = ">=3.12"`; the venv is 3.14.3.** `uv` and pytest. No new dependency.
- **`axiom:main` stays the packaging entry point.**
- **The repo's own rules apply**: KISS over structure, one command per shell invocation,
  nothing committed under a `temp` name, project-local `.tmp/`, loop files stay in this folder
  while code stays in `src/` and `tests/`.
- **The branch is `feature/49-model-switch`.** Commits reference #49.
- **`master` is protected by a hook** - commits on it are blocked. Everything lands on the
  branch and merges by PR.
- **This is the last row in the queue.** A converged run says the queue is finished rather than
  scaffolding nothing silently, and says that **manual testing is next** - see
  `.claude/handoff.md`, which has been true and unactioned since 2026-08-26.

## Decided - do not reopen

Settled with Kaushik on 2026-08-27, before the issue was written.

- **The conversation carries across a switch.** Not cleared. The point of switching is that the
  new model can see the question.
- **`/model` shows the list; `/model <name>` switches directly.** Both are the user picking,
  and **both are remembered** - which is consistent with #48 AC 14 rather than an exception to
  it, because that rule is about a launch flag, not about something typed at the prompt.
- **A name must match exactly, tag included.** `qwen2.5` does not find `qwen2.5:7b`. Ollama
  would read a bare name as `:latest` and land on a different model, which is the failure both
  stories exist to prevent. A near-miss falls through to the list.
- **Ctrl-C at the list cancels the switch; Ctrl-D ends the session.** Different on purpose, and
  different from #48 where both leave - there, no session exists yet to return to.
- **Tool history carries across unchanged** even into a model that cannot call tools. Kaushik's
  call: a user who does not ask for tool work again will be fine, and rewriting history is
  worse than carrying it.
- **A conversation that cannot fit the new model is reported, and `/model` remains available**
  to move to one that can. No automatic revert.

## Carried forward, worth not relearning

- **Probe before designing.** Every decision probed first has held; the ones reasoned from code
  alone were wrong.
- **A test can prove the happy path of a criterion and miss the criterion.** Five issues
  running.
- **Fix every stub before regenerating the transcript.** #48 wrote a golden master full of
  `AttributeError` and only the copy-aside made it recoverable.
- **A `sed`/`.replace()` that does not match reports success.** #48 reset a fail-safe clock and
  left one line saying the opposite of the line above it. Grep after scripted edits.
- **The formatter is not the only thing that edits a file.** Verify what landed.
- **Two facts with different fixes get two sentences.** #48 reused one message for a vanished
  model and a corrupt file and produced nonsense that its own test accepted.

# Assumption

Standing inputs. These are given - do not re-derive them, and do not spend a cycle deciding
them.

## The codebase this lands in

Every earlier row merged. **317 tests, green and hermetic** at scaffold time.

- **`config.DEFAULT_MODEL = "qwen2.5:7b"` at `config.py:12` is what this issue deletes.**
  `parse_args` uses it as the `--model` default behind `$AXIOM_MODEL`. AC 2 is met when it is
  gone and nothing under `src/` names a model.
- **`backend.ModelBackend` is a Protocol with `model_info`, `supports_tools`, `stream` and
  `complete`.** `OllamaBackend` implements it and is **the only module under `src/` that
  imports a vendor client**. Listing models is a fifth method on that protocol. This is not
  optional: the test stubs implement the protocol, and it is what keeps the suite runnable
  with no Ollama.
- **`OllamaBackend.model_info` and `supports_tools` both swallow errors** - returning `None`
  and `False` on `ResponseError`, `ConnectionError` and `httpx.HTTPError`. That swallowing is
  precisely why a missing model is silent today. A listing method that does the same would
  make AC 31 and AC 32 unreachable, because "cannot reach the host" and "the host has no
  models" would look identical.
- **`terminal.py` owns every `print()` and the only `input()`.** The list, the question, the
  refusals and the announcements all belong there; `__init__.py` asks it to say things.
- **`main()` returns `None` and nothing in axiom has ever exited non-zero.** `sys.exit` does
  not appear under `src/`. AC 31, 32 introduce the first non-zero exits, and `axiom:main` is
  the packaging entry point, so whatever is chosen has to carry a status through it.
- **`config.read_servers(path)` is the pattern for reading a file that may be wrong**: it
  returns problems rather than raising, because a bad entry costs that server and not the
  session. AC 33 and AC 34 want exactly this shape.
- **`.axiom/mcp.json` is the existing config file**, resolved as `Path(".axiom")/"mcp.json"`
  relative to the working directory. The remembered choice lives in the same folder and is a
  **different file**.
- **`tests/conftest.py`** holds `StubBackend`, `feed()`, `chunk()`, `vendor_call()`,
  `history()` and the autouse fixture clearing `AXIOM_HOST`, `AXIOM_MODEL` and
  `AXIOM_DEBUG_MAX_CONTEXT`. `StubBackend` gains the listing method.

## The Ollama API, measured 2026-08-27

Do not re-research this. `curl http://localhost:11434/api/tags` was run at scaffold time.

- Each model carries `name`, `model`, `modified_at`, `size`, `digest`, `capabilities`, and
  `details` with `parameter_size`, `quantization_level` and sometimes `context_length`.
- **The order is `modified_at` descending** - newest first. It is not sorted and it is not
  stable: pulling or re-pulling any model moves it to the front and renumbers everything
  after it. **This is the fact AC 6 exists for.**
- `capabilities` includes `tools` for models that can call them - the same field
  `supports_tools` already reads.
- **Ollama has no concept of a default model.** There is no server-side default to ask for,
  which is why AC 11 and AC 19 fall back to the first entry.

## The local Ollama, and what testing may use it for

`http://localhost:11434`, five models installed:

| model | parameter size | tools |
|---|---|---|
| `gemma2:2b` | 2.6B | **no** |
| `gemma4:e2b` | 5.1B | yes |
| `ornith:9b` | 9.0B | yes |
| `qwen2.5:7b` | 7.6B | yes |
| `qwen2.5-coder:7b` | 7.6B | yes |

**Kaushik has asked that development and hands-on testing use this local Ollama.** That means
the implementer runs axiom against it to see the picker behave. It does **not** loosen the
hermeticity rule: every criterion is settled against a stub, and the suite must pass with
nothing running. A test that needs a live host is the failure mode this row is most exposed
to, because the whole issue is about asking a host a question.

`gemma2:2b` is the only model here with no tool support, which makes it the instrument for
the "this model cannot call them" path.

## Given

- **`requires-python = ">=3.12"`; the venv is 3.14.3.** `uv` and pytest.
- **No new dependency is needed.** `ollama` already provides the listing call.
- **`axiom:main` stays the packaging entry point.**
- **The repo's own rules apply**: KISS over structure, one command per shell invocation,
  nothing committed under a `temp` name, project-local `.tmp/`, loop files stay in this folder
  while code stays in `src/` and `tests/`.
- **The branch is `feature/48-model-choice`.** Commits reference #48.
- **`master` is protected by a hook** - commits on it are blocked. Everything lands on the
  branch and merges by PR.
- **#49 is queued behind this row** and depends on it: the switch list must match this list,
  and a switch is remembered by this row's mechanism. Build both so a second story can reuse
  them, but do not build #49's command here.

## Decided - do not reopen

Settled with Kaushik on 2026-08-27, before the issue was written. Implement them; do not
re-decide them, and do not spend a cycle rediscovering the reasoning.

- **The picker appears only when no model was named.** A flag or environment variable naming
  an installed model starts the session silently.
- **With exactly one model installed, nothing is asked.** It is chosen and announced.
- **When input is not a terminal, nothing is asked, ever**, and the session still runs - the
  remembered choice for that host if installed, else the first model.
- **A named model the host does not have is reported, then treated as though it had not been
  named.** This is a deliberate, announced fallback. It **supersedes #26 AC 14**, which
  forbade falling back; a comment recording that is already on #26.
- **Sort the list by model name.** Alphabetical is the stable order AC 6 asks for. Note the
  consequence on this machine: the alphabetically first model is `gemma2:2b`, which has no
  tool support, so a first-ever run with nothing named and nothing remembered lands on a
  model that cannot call tools. It is announced, it is one keystroke to change, and it is
  remembered thereafter. **If a cycle finds this genuinely bad in use, say so in the log as a
  finding for Kaushik - do not quietly sort by something else.**
- **The remembered choice is per host and per directory**, stored in `.axiom/` beside
  `mcp.json`, keyed by host.
- **Only a model the user picks themselves is remembered.** Not a flag, not an environment
  variable, not the single-model case, not the non-terminal fallback.
- **`.gitignore` gets an entry for the remembered-choice file specifically** - never a blanket
  `.axiom/`, because `mcp.json` is designed to be committed and `${NAME}` substitution exists
  to make that safe.

## Carried forward, worth not relearning

- **Probe before designing.** Every significant decision in #34, #35, #40, #41, #42 and #43
  that was probed first held; the ones reasoned from the code alone were wrong.
- **A test can prove the happy path of a criterion and miss the criterion.** #40 AC 7, #41
  AC 9, #42 AC 3 and #43 AC 6 were all marked met by tests that could not have failed.
- **A stub that contradicts the thing under test proves nothing.**
- **Read a diff as a diff**, and check for removed lines explicitly.
- **Check which function a number came from.** `estimated_tokens` divides by four and
  `too_large` by three.
- **The formatter is not the only thing that edits a file.** A `PostToolUse` hook stripped
  four imports in #43 between the edit that added them and the edit that used them. Verify
  what landed.
- **A scripted `.replace()` that does not match reports success.** Verify scripted edits.

# Assumption

Standing inputs. These are given - do not re-derive them, and do not spend a cycle deciding
them.

## The stack, settled by research on 2026-08-27

Researched with Kaushik before the issue was written. **Do not re-open it.**

- **Rich, inline.** It renders markdown, syntax-highlights code, and draws inline - no alternate
  screen, so scrollback, selection and piping all survive.
- **Textual was rejected**, and the reason is structural rather than aesthetic: it is async-first
  with its own message pump, and `servers.py` already runs a background event-loop thread
  *specifically* so the rest of axiom can stay synchronous. Adopting Textual would put a second
  event loop in the process and re-open the one decision #43 spent a cycle getting right. It also
  takes the alternate screen, which would make `echo "hi" | axiom` a different program.
- **Claude Code is inline**, not a full-screen TUI. "Look like Claude Code" points at Rich.
- **`prompt_toolkit` and the input line are a separate story that has not been written.** Not
  this row.

**Prior art to read before writing a line** - all three solve streaming markdown, and all three
are *applications* rather than importable libraries, so they are references and not dependencies:

- `md2term` - https://github.com/statico/md2term
- `richify` - https://github.com/gianlucatruda/richify
- the merged PR on `simonw/llm` - https://github.com/simonw/llm/pull/571/files

## The codebase this lands in

Rows 1 to 15 merged. **539 tests, green and hermetic** at scaffold time.

- **`terminal.py` is the only module under `src/` that calls `print()` or `input()`.** That seam
  is why this row is possible without touching the chat loop, and it was built for exactly this.
- **`terminal.show_piece(text)`** prints a fragment with `end=""` and `flush=True`. It is called
  once per streamed chunk with `reply[shown:]` - the *new* text only.
- **`terminal.end_reply()`** prints the newline that ends a streamed reply.
- **`_could_still_be_a_call(reply)` in `__init__.py`** holds the whole reply back while it could
  still turn out to be a bare-JSON tool call, then either recognises a call or prints the lot.
  **A renderer sits on top of conditional withholding**, which is where AC 20's risk is.
- **`terminal._accept_any_character`** reconfigures stdout/stderr to `utf-8, errors=replace` on
  import - a Windows console is cp1252 and a single emoji would otherwise kill a finished answer.
  Confirmed live during manual testing when a model emitted a green circle.
- **#58 owns the blank lines**: `start_turn()` after the user's line, `end_turn()` at all four
  ways a turn ends. AC 21 must not disturb them.
- **The golden transcript captures non-terminal output.** If the piped path stays plain, it does
  not change.
- **`tests/test_terminal.py`** holds the startup-line coverage; `tests/test_spacing.py` holds
  #58's.

## Given

- **`requires-python = ">=3.12"`; the venv is 3.14.3.** `uv` and pytest.
- **`rich` is the one new dependency this row is allowed**, and it is the reuse the repo rules
  ask for - do not hand-roll a markdown parser. Pin it in `pyproject.toml` and record the
  version.
- **The repo's own rules apply**: KISS over structure, one command per shell invocation,
  nothing committed under a `temp` name, project-local `.tmp/`, loop files stay in this folder
  while code stays in `src/` and `tests/`.
- **The branch is `feature/60-rendered-replies`.** Commits reference #60.
- **`master` is protected by a hook.** Everything lands on the branch and merges by PR.
- **This is the last row in the queue.** A converged run says so rather than scaffolding nothing
  silently, and hands to `.claude/handoff.md` - **manual testing is still unfinished**: #41, #34,
  #40, #35 and #26 were never reached.

## Decided - do not reopen

- **Inline, never the alternate screen.**
- **Plain text when output is not a terminal**, byte-identical to today. Kaushik confirmed this
  explicitly. It keeps the tests honest and `axiom | grep` working.
- **Streaming, not buffered.** Kaushik chose progressive rendering over rendering once the reply
  completes, knowing that is where the complexity lives.
- **Rendering never changes what is sent to the model or kept in history.**
- **A rendering failure costs the formatting, never the answer.**

## Carried forward, worth not relearning

- **A single flattering sample is not evidence.** #62 nearly adopted the wrong conclusion from
  three one-run probes; the run-to-run variance was as large as the effect. **This row has a
  judgement component and is more exposed to this, not less.**
- **An assertion a wrong implementation also satisfies proves nothing.** #61's AC 9 had none at
  all while 520 tests stayed green.
- **A test asserting more than its criterion** breaks when something correct lands. #61 found two.
- **Fix every stub before regenerating the transcript** - and here, expect not to regenerate at
  all.
- **A `sed`/`.replace()` containing a backslash escape will not match.** Use the editor. #62 lost
  two attempts to this in one cycle.

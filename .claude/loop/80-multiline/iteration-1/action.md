# Action — cycle 4

**First, finish what cycle 3 left unproved. Then the composing display.**

## 1 — Three breaks that did not prove anything

AC 1, 2 and 18 are implemented, their tests are green, and they are **not counted**. Close
that before adding anything.

- **AC 1 and AC 2's breaks did not apply.** The harness's search strings were mangled by
  escaping. **Write the harness through the Edit tool**, not a heredoc — the source contains
  `insert_text("\n")` and that is exactly the case the rule is about.
- **AC 18's break was wrong, not its test.** `multiline=False` still lets `insert_text` put a
  newline in the buffer, so the criterion was never violated and the test was right to stay
  green. Find a break that actually stops a blank line surviving.

**Every break must be given an end before it runs.** Cycle 3 lost the file twice to a reader
waiting for a key that never came; `create_pipe_input` is now closed in the test helper,
which is what makes a broken binding fail in milliseconds rather than hang.

## 2 — What the user sees while composing

AC 4, 5, 22, 23. These are the criteria a test can only half-reach, so be explicit in the log
about which half:

- **AC 4** — every line of the message is visible before it is sent.
- **AC 22** — it is apparent the message has not been sent yet.
- **AC 23** — the user can tell how many lines it has, or see them all.
- **AC 5** — the first time a second line is started, axiom says how to send and how to add
  another. Said **once**, not on every line; a hint that repeats is noise by the third time.

`prompt_toolkit` draws a continuation prompt for lines after the first, which is most of
AC 4 and AC 22 for free. Check what it draws by default before writing one.

## Do not

- Touch paste handling. That is AC 7, 8, 9 and it is the hardest thing in the issue.
- Regenerate the baseline.

## Still owed

`uv.lock` does not list `prompt_toolkit`. The package went in with `uv pip install` because a
live axiom session held `.venv/Scripts/axiom.exe`. **Run `uv lock` if nothing is holding it**;
if something still is, carry this forward rather than dropping it — a lockfile that disagrees
with `pyproject.toml` surfaces on someone else's machine, not this one.

## Record

`logs/cycle-4.md`, per `observe.md`. Criteria out of 36, suite count and wall-clock, the
baseline's state, and the running list of what only a person can confirm.

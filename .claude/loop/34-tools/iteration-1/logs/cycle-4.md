# Cycle 4 - 2026-08-25 06:52 IST

The remaining file tools and the command tool. **106 tests green, from 87.** `src/` 656 -> 828.

The transcript's sixteen scenarios are unchanged - adding tools changed no existing behaviour.

## Five tools now

`read_file`, `write_file`, `edit_file`, `delete_file`, `run_command`.

`edit_file` **refuses text that appears more than once.** The model asked to change one thing;
silently changing three would be a different edit than the one it described to the user. AC 11
is tested as exact bytes with CRLF line endings, so an implementation that rewrote the whole
file would fail rather than pass a looser comparison.

`delete_file` is tested by calling it directly, never by asking a live model - AC 12 settled
the way `CLAUDE.md` requires while no security layer exists.

## A hardening that fell out

`run()` now refuses arguments the tool never declared. It was written so a model cannot reach
a keyword the schema does not offer it - the command time limit belongs to the user, not to
the model, and `run(**arguments)` would otherwise splat whatever the model invented straight
into the function.

## The command tool, and the bug the tests caught

Two tests failed on the first implementation, and they are the reason the timeout tests were
written to check the process rather than the message.

**`subprocess.run(..., shell=True, timeout=...)` does not do what it appears to on Windows.**

With `shell=True` the child is `cmd.exe`, and the program the user asked about is its
*grandchild*. On timeout, `subprocess.run` kills the shell - and the grandchild survives. It
also inherited the stdout pipe, so the follow-up `communicate()` blocks until *it* finishes.

Measured, not theorised: a 0.5-second limit on a 30-second sleep took **36.5 seconds** and
then reported `stopped it` - while the command was still running, and went on to write its
file two seconds later. Both halves are bad on their own:

- The user is told a command was stopped when it was not.
- A hung command hangs axiom for its full duration, which is exactly what AC 27 exists to
  prevent.

`test_a_stopped_command_is_actually_killed` is what caught it: it has the command write a
marker file after the timeout should have killed it, then checks the marker never appears.
A test that only asserted `"stopped" in result` would have passed against a program that
lies.

**Fixed with `psutil`, which is already a dependency** - reuse before build. `run_command`
now uses `Popen`, and on timeout kills the whole tree, children first, before draining the
pipes.

Evidence the fix is real: the same test file went from **36.56s to 5.10s**. The timeout now
stops at half a second instead of waiting out the full thirty. The timing is the proof.

## Criteria status

**Startup** 1 `not-started`, 2 `attempted`

**Works across models** 3 `not-started`, 4 `met-with-evidence`, 5 `attempted`,
6 `not-started`, 7 `not-started`, 8 `attempted`

**Files**
9. `met-with-evidence` - creates it, names the path, makes missing parents
10. `met-with-evidence`
11. `met-with-evidence` - byte-identical, CRLF preserved, and refuses a non-unique match
12. `met-with-evidence` - stub-driven inside `tmp_path`

**Commands**
13. `met-with-evidence`
14. `met-with-evidence` - and a test asserts no allowlist exists, so a future one has to
    delete a test rather than quietly appear
15. `met-with-evidence` - both streams, and stderr is labelled so the user knows which
16. `met-with-evidence` - status named, output before the failure still returned

**Multi-step work** 17-19 `met-with-evidence`, 20 `not-started`

**Visibility** 21-23 `met-with-evidence`

**Boundaries**
24. `met-with-evidence`
25. `met-with-evidence`
26. `met-with-evidence` - "(finished with no output)", not an error
27. `met-with-evidence` - stopped at the limit, **and the process is provably gone**

**Failure and recovery** 28 `met-with-evidence`, 29 `met-with-evidence`,
30 `not-started`, 31 `not-started`

**Configuration**
32. `attempted` - `WORKING_DIRECTORY` works and is tested; its default, override and
    visibility are not wired to config yet
33. `attempted` - same for `COMMAND_TIMEOUT_SECONDS`
34. `not-started`

**Exit** 35 `met-with-evidence`

## Goal check

**Not met.** 24 of 35 carry evidence, from 16.

## What is still missing

Eleven criteria, in three groups, and none blocked:

- **Configuration and startup** - AC 1, 2, 32, 33, 34. One cycle: wire `config.Settings` to
  the two tool constants, add the startup line, regenerate the transcript deliberately.
- **Interrupt and failure reporting** - AC 30, 31. Ctrl-C during a running tool, and telling
  a tool failure apart from a model failure.
- **The live model criteria** - AC 3, 5, 6, 7, and AC 8 finishing. These cannot be closed
  with stubs and want a cycle of their own, with model swapping budgeted for.

AC 20 - compaction treating tool calls as history - is the quiet one. `compacted_history`
summarizes `{role, content}` pairs; a `tool_calls` key is not `content`, and an assistant
message carrying only calls has `content=""`. Nothing has checked what compaction does with
that.

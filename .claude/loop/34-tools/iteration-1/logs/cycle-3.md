# Cycle 3 - 2026-08-25 06:37 IST

Tests for what cycle 2 built. **87 tests green, from 66.** `src/` 651 -> 656.

No new tools, no startup-line change - both deferred deliberately.

## `tests/test_tools.py` (10)

Direct against `tools.run()` and `declarations()`. No model, no backend, everything inside
`tmp_path`.

Covers AC 4 (declarations take no model argument - asserted with `inspect.signature`, so a
future `declarations(model)` fails the test rather than passing review), AC 10, AC 24, AC 25
and AC 29.

`test_running_a_tool_never_raises` is the one that matters most: the turn loop calls `run()`
without a `try`, so anything escaping it ends the session, which is what AC 28 forbids. It
feeds a directory, an empty string, `None`, and an unknown tool name. All four come back as
messages.

## `tests/test_tool_loop.py` (11)

Through `main(..., using=stub)`. `StubBackend` now yields a `Call` when it finds one in its
turns, so the whole loop is drivable without a model.

Two proved things the live run in cycle 2 only suggested:

- **The rollback.** Cycle 2 changed `messages.pop()` to `del messages[before:]` and never
  tested it. A turn that reads a file and *then* loses the connection must leave nothing -
  not the user's line, not the assistant turn, not the tool result. The test drives exactly
  that, then checks the next request carries only the new question. A half-finished turn left
  in history would be replayed to the model as though it had happened.
- **Truncation is a screen concern only.** `TOOL_OUTPUT_LIMIT` shortens what is printed; the
  model still receives all 5000 characters. Shortening what the model is told would silently
  change the answer it gives, and nothing else in the suite would have noticed.

Also: `MAX_TOOL_ROUNDS` is asserted to actually bound a model that answers every result with
another call, and tools are asserted absent from the request when the model cannot use them.

## A display defect the tests found

`note_tool` used `{value!r}`, so a Windows path printed as
`read_file(path='C:\\Users\\hazra\\...')` - every backslash doubled. Cycle 2's live run hid
it because the model happened to emit forward slashes.

That is not what the user typed and not what they would type to check it. Changed to plain
`{value}`. Real usage on Windows would have hit this constantly.

## The transcript grew, deliberately

Three scenarios added: a tool running and answering, a tool failing and the turn carrying on,
and a model with no tool support still chatting.

**The regeneration was purely additive, and that is proved rather than asserted.** The old
baseline was copied aside first, and `diff` afterwards reports:

```
117a118,148
```

An `a` at line 117 and nothing else - no deletions, no changes. All thirteen original
scenarios are byte-identical.

### One thing had to be normalised

The tool scenarios need a real file, so they get a fresh `mkdtemp` directory - whose path is
in the printed output and different on every run. Recorded verbatim, the transcript would
fail on its own next run.

`_stable()` replaces the sandbox path with `<sandbox>` before comparison. **The path is
environment, not behaviour**; everything else is still recorded exactly as printed. Proved by
running the whole suite twice, each with a fresh temp directory, both green.

### And one near-miss worth recording

`_stable()` did not land on the first attempt. A scripted `.replace()` silently failed to
match - the escape sequences in the replacement had been mangled - and the baseline was
regenerated *with raw machine-specific paths in it*. The `diff` is what caught it, because
the paths were visible in the output being reviewed.

Had the regeneration been done without diffing against the old file, a transcript that fails
on every machine but this one would have been committed. **That is the argument for the
diff-before-commit step, and it earned itself this cycle.**

## Criteria status

**Startup** 1 `not-started`, 2 `attempted`

**Works across models**
3. `not-started` - still only `qwen2.5:7b` live
4. `met-with-evidence` - now enforced by a test, not just by inspection
5. `attempted`
6. `not-started`
7. `not-started`
8. `attempted`

**Files** 9 `not-started`, 10 `met-with-evidence`, 11-12 `not-started`

**Commands** 13-16 `not-started`

**Multi-step work**
17. `met-with-evidence` - one line typed, two model turns, no second prompt
18. `met-with-evidence`
19. `met-with-evidence`
20. `not-started`

**Visibility** 21 `met-with-evidence`, 22 `met-with-evidence`, 23 `met-with-evidence`

**Boundaries**
24. `met-with-evidence` - missing file explains itself, session continues
25. `met-with-evidence` - empty reads as empty, not as an error
26-27. `not-started` - commands do not exist yet

**Failure and recovery**
28. `met-with-evidence` - failing tool, turn carries on, and `run()` provably never raises
29. `met-with-evidence` - unknown tool, wrong arguments, missing arguments
30. `not-started`
31. `not-started`

**Configuration** 32-34 `not-started`

**Exit** 35 `met-with-evidence`

## Goal check

**Not met.** 16 of 35 carry evidence, from 8.

## What is still missing

The mechanism is now tested rather than merely demonstrated. What remains splits cleanly:

- **More tools** - create, change, delete a file; run a command. AC 9, 11-16, 26-27.
- **The startup line and configuration** - AC 1, 2, 32-34, where the transcript changes again.
- **The model-facing criteria** - AC 3, 5, 6, 7, and AC 8 finishing. These need live runs
  against all three families and are the ones a stub cannot close.

The commands tool is the one carrying real risk, because it is where the safety rules bite
hardest and where a timeout, a non-zero exit and a hung process all have to behave.

# Cycle 3 — the cold read

2026-08-27 14:05–14:35 IST. Fail-safe 16:27 IST.

Criteria read from `gh issue view 48` **before** the diff and before cycle 2's log, and
attacked rather than confirmed. **377 tests, green and hermetic** (was 369).

Not a genuinely fresh reader - no second agent was used, and `observe.md` asks that this be
said rather than a cold read claimed that was not cold. The compensation was mechanical:
every finding below came from running something hostile, not from rereading code, and each
fix is paired with a break-and-watch proving the test can fail.

## Five for five — the cold read found real defects again

### 1. The broken-choice-file message was nonsense, and its test passed on it

AC 33 says a choice file that cannot be read is *said*. It was - by reusing
`note_choice_forgotten`, which is AC 15's message:

```
axiom: your saved choice was your last choice here but http://localhost:11434 no longer has it
```

Two things wrong. It is not a sentence, and it **blames the host for removing a model** when
the truth is a corrupt local file the user can open and fix. Cycle 2's test asserted only
`"saved choice" in out.err` — which that string satisfies. A test that passes on gibberish.

Fixed with `note_choice_unreadable(path)`, which names the file, says it could not be read,
and says nothing about the host. The test now asserts the path appears, that
`"could not be read"` appears, and **that `"no longer has it"` does not** — so the two
messages can never be conflated again.

### 2. AC 29 had no test at all, because the stub could not tell

"The context window and tool count reported at startup belong to the model in use." Cycle 2
believed this covered by a startup-line assertion. It is not: `StubBackend.model_info` and
`supports_tools` **discarded the model name they were handed**, so asking about the wrong
model entirely would print an identical startup line and pass.

Same class as `given_page` announcing `text/plain` over HTML in #40, and the constant
`prompt_eval_count` in #41 — a stub contradicting the thing under test.

`StubBackend` now records `asked_about`. Three tests assert the backend was interrogated
about the settled model and no other. **Break-and-watch:** changing `supports_tools(model)`
to `supports_tools(settings.model or model)` turned
`test_a_missing_named_model_is_never_asked_about` red, and reverting restored it.

### 3. AC 13 was tested as a path shape, not as behaviour

The criterion is "running axiom from a different directory has its own remembered choice."
The test asserted the constant was relative — true, and not the claim. Added a test that
`chdir`s into two directories, picks differently in each, and asserts neither file can see
the other.

### 4. AC 1 was ordered against the wrong event

The test asserted the startup line came after the question — which passes for an
implementation that starts every server first and merely prints tidily. Rewritten to
configure a server that is really attempted, then assert `starting 1 MCP server` appears
**after** the question and not before. **Break-and-watch:** hoisting
`terminal.note_starting(...)` and `attached.start()` above `_settle_model` turned it red.

### 5. A blank model name reached the screen as a message with a hole in it

Not from the criteria — from asking what a user actually types.

```
$ axiom --model "   "
axiom:     is not installed on http://localhost:11434
```

`AXIOM_MODEL=` — how a shell unsets a variable — was *accidentally* correct: the empty string
is falsy, so `if decision.missing:` skipped the message and the run fell through to the
no-model-named path. Right behaviour for the wrong reason, and whitespace is truthy, so the
same path printed a sentence with a gap in it.

`config.resolve` now normalises a blank name to `None`, making the empty case deliberate
rather than lucky. Five new tests.

## Dead code removed, because it contradicted the criteria

`terminal.ask_model` carried an `"a number"` hint for when nothing was marked as default, and
`refuse_model` a third branch saying "there is no default to take". **Neither can execute.**
`choose()` returns `default=preferred or available[0]` on the interactive path, and that path
is reached only with two or more models — so something is always marked.

They encode an *earlier draft* of the issue, where a missing remembered model left nothing
marked and enter was refused. The final AC 9 and AC 15 say the opposite: exactly one entry is
always marked, and a vanished remembered model hands the mark to the first entry. Untestable
code asserting the reverse of the criterion is worse than no code. Removed; both signatures
lost their `default` parameter.

## Vacuous-test sweep — could this pass if the feature did nothing?

Asked of every criterion that asserts on an absence, and settled by breaking the feature.

| broken | tests that went red |
|---|---|
| `_remember` called on every route, not only a user's pick | **5** — all four AC 14 negatives, plus the flag-does-not-overwrite case |
| `sorted_models` returns the host's order unchanged | **18**, including both dedicated AC 6 order tests |
| `supports_tools` asked about the named model | 1 — AC 29's missing-name case |
| servers started before settling | 1 — AC 1 |

Every negative assertion in this row now has a matching positive proving the write path works,
so "the file does not exist" cannot pass by nothing ever being written.

## Status — all 38 criteria

| criteria | status |
|---|---|
| AC 1–38 | `met-with-evidence` |

Each has a test in `tests/test_models.py` or `tests/test_config.py`, cited by number in its
docstring. AC 2 is settled by a source-level grep for a `family:tag` literal rather than by a
behaviour test, because a leftover default would sit unused on the happy path and pass
anything behavioural.

## Standing checks

- **377 passed**, hermetic: `AXIOM_HOST=http://127.0.0.1:1 AXIOM_MODEL=nonsense:99b
  AXIOM_DEBUG_MAX_CONTEXT=7`. No test reaches a live Ollama.
- **Transcript: 27 added lines, `grep -c "^<"` = 0.** Unchanged since cycle 2 — the fixes
  here touched no line the transcript records.
- No orphaned processes; no `.axiom/` left in the repo.

## Carried to #49

- `StubBackend.asked_about` exists now, and #49 AC 16 — tool availability following a switch —
  is the same class of claim AC 29 was. Use it rather than trusting a printed line.
- The startup list, its sorting, and `models.picked` are reusable as-is. #49 AC 2 asks the
  switch list to match this one; it should call the same functions, not a copy.
- `note_choice_unreadable` versus `note_choice_forgotten` is the shape to keep: two facts with
  different fixes get two sentences. #49 will be tempted to reuse a message again.

## Exit

Converged — `loop.md` exit 1. All 38 criteria met with evidence, suite green and hermetic,
transcript accounted for. Commit, push, PR referencing #48, merge, delete the branch, then
hand over to row 10.

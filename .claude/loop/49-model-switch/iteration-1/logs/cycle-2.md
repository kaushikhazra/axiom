# Cycle 2 — implementation

2026-08-27 14:05–14:40 IST. Fail-safe 16:52 IST.

**413 tests, green and hermetic** (was 377). 35 new in `tests/test_switch.py`, one new in
`tests/test_oversized_turn.py`, two amended there.

## What landed

| file | change |
|---|---|
| `__init__.py` | `Running` + `_prepare` (the refactor), `MODEL_COMMAND`, `_LEAVING`, `_switch_model`, `_switched_to`. |
| `terminal.py` | `note_switched`, `note_unchanged`, `note_only_model`, `report_switch_failed`; `show_models` gained `current`; `ask_model` now **raises** instead of swallowing. |
| `servers.py` | `started` property; `start()` made idempotent. |
| `tests/conftest.py` | `StubBackend` gained `infos` and `capable` - per-model answers. |

## The refactor came first, and paid immediately

`Running` holds the six things that belong to the model - `model`, `capable`, `declarations`,
`callable_names`, `context`, `options` - and `_prepare` builds it. Startup and switch call the
same function, so **the two paths cannot drift**, and a switch is one assignment rather than
six. Updating five of six is the failure mode separate rebindings invite, and it would be
silent.

Landed as its own step and **the suite stayed at 377 green including the byte-identical
transcript**, which is what makes it a refactor rather than a rewrite.

Everything *not* in `Running` is deliberately not in it. `messages`, `limits`, `attached` and
`instructions` are untouched by a switch, and keeping them out of the object makes AC 13 and
AC 14 structural rather than remembered.

## Decisions made this cycle

- **`ask_model` raises instead of returning None.** The two callers want different things from
  the same keystroke: at startup Ctrl-C and Ctrl-D both mean leave, while mid-conversation
  Ctrl-C means "never mind" and Ctrl-D means input ended. One `None` for both could not tell
  them apart (AC 26, AC 33).
- **`_switch_model` is a sibling of `_settle_model`, not a reuse of it.** Four behaviours
  differ: it must not exit on a bad host, Ctrl-C cancels, the marked entry is the *current*
  model, and it can never settle without asking. What they *do* share is
  `models.sorted_models`, `models.picked` and `terminal.show_models` - which is the whole of
  AC 2.
- **Enter at the switch list keeps the current model** rather than re-selecting it. At startup
  enter accepts a default; here there is nothing to accept, and a switch nobody asked for is
  worse than a wasted keystroke.
- **`running_usage` resets to None on a switch**, per cycle 1. Named by no criterion.

## A criterion of #42 had to be superseded

**AC 19 collides with #42 AC 6.** #42 ended the session when the context could not hold even
an empty message, and was right to: nothing the user typed could fit, so repeating the line at
every prompt *was* the discovery-by-retrying it existed to prevent, and ending was what made
#42 AC 4 true - no state where every message is refused, because there are no more messages.

`/model` changes the premise. The window belongs to the model, and a switch keeps the
conversation, so the wall is now escapable **without losing anything**. So:

- The message names the model that cannot hold it and the command that fixes it.
- The session stays.
- #42 AC 4's protection survives in a better form - there is a way out that is not "type less."

Two #42 tests were amended and one added
(`test_a_session_that_cannot_continue_still_accepts_a_switch`, which proves the way out
actually works rather than merely being mentioned). **This is a deliberate supersession,
recorded here and in the test docstrings**, not a test bent to fit new code.

## An ambiguity settled, and the crash it was hiding

Servers start only when a model can call tools, so a session beginning on `gemma2:2b` has none
running. AC 16 promises the new model's tools after a switch - but there was nothing to
restore.

Took the **lazy start**: `_prepare` starts them on first need. That preserves #43 for every
existing user, spends no subprocess a tool-less session will never use, and AC 14 stays true
because nothing already running is touched.

**`Servers.start()` was not idempotent** - it spawns a thread, and a second call raises
`RuntimeError: threads can only be started once`. Guarded. Break-and-watch confirms it: with
the guard removed, `test_running_servers_are_not_restarted` fails with exactly that
`RuntimeError` - **a crash mid-conversation, for asking twice.**

## A test of my own that did not test what it said

`test_tool_calls_already_in_history_carry_across_unchanged` describes switching into a model
that **cannot call tools** - and the stub said every model could, so the printed line read
`now gemma2:2b (context: Ollama default, 7 tools)`. It passed, and proved nothing about the
case its name describes.

Caught by reading the output of a *different* break, not by rereading the test. Fixed with
`capable={"qwen2.5:7b": True, "gemma2:2b": False}` and an added assertion that
`tools_sent[-1] is None`.

This is why `StubBackend` gained `infos` and `capable` at all: a single answer for every model
cannot show that a switch adopted the **new** model's window or support. AC 15's test now uses
32768 and 4096 and asserts both.

## Break-and-watch

| broken | went red |
|---|---|
| history cleared on a switch | **2** — AC 10, AC 11 |
| `start()` guard removed | 1 — AC 14, with `RuntimeError` |
| Ctrl-C treated as Ctrl-D | 1 — AC 26 |

## Transcript

**Two removed lines, both replacements, and every one accounted for:**

```
< >                                          ->  > > >      (prompt returns, session no longer ends)
< error: this session cannot continue ...     ->  error: qwen2.5:7b cannot hold ... Use /model ...
                                                  (and again, because it can now repeat)
```

Nothing else changed and no scenario was lost. The stubs were fixed **before** regenerating -
#48 cycle 2 did it the other way and wrote a golden master full of `AttributeError`.

## Live against the real Ollama

```
> /model gemma2:2b
axiom: now gemma2:2b (context: 8192 tokens, no tools - this model cannot call them)
> /model
  1. gemma2:2b  (current)
  ...
axiom: which model? (enter to keep the current one) 3
axiom: now ornith:9b (context: 30606 tokens, 7 tools)
> /model qwen2.5
axiom: qwen2.5 is not installed on http://localhost:11434
  ... the list ...
```

**AC 16 confirmed live in both directions** - tools dropped moving to `gemma2:2b`, restored on
`ornith:9b`. **AC 7 confirmed live**: `qwen2.5` did not resolve to `qwen2.5:7b`. The window is
genuinely per-model: 32768, 8192, 30606, 131072.

## Status — all 34 criteria

| criteria | status |
|---|---|
| AC 1–34 | `attempted` |

Not `met-with-evidence`. This is the cycle that wrote the code, and it does not get to declare
it done - even though it already ran a break-and-watch sweep. Cycle 3 reads the criteria from
GitHub first.

## Cycle 3 will

Cold-read all 34 against the issue text. The likeliest gaps, judging by what cycle 2 had to fix
in itself: criteria asserted on printed output where a payload or an `asked_about` fact is
available, and any test whose name promises a condition the stub does not actually create.

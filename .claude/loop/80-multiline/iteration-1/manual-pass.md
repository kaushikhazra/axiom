# #80 — the manual pass

**Fifteen of the thirty-six criteria are yours. The other twenty-one are proved by test,
each one broken and watched going red.**

The automated tests that pressed keys are gone (commit `32daf51`). They built a real
`prompt_toolkit` session, and `_say_how_to_send` reaches the *real* console through
`run_in_terminal` rather than the `DummyOutput` the test supplied — which is how a pytest run
escaped into the session that launched it and took the machine down twice.

So the key presses are checked here, by hand, at a real terminal. Run it as `axiom` in a
normal terminal — not through a pipe, not inside a harness.

## Proved by test — do not re-check by hand

AC 5, 11, 13, 14, 15, 16, 17, 19, 20, 21, 22, 23, 28, 29, 30, 31, 32, 33, 34, 35, 36.

## What a person has to look at

| AC | What to do | What should happen |
|---|---|---|
| 1 | Type `first`, ctrl+enter, `second`, enter | One message arrives with both lines |
| 2 | Type a word, press ctrl+enter | The cursor drops to a new line; **nothing is sent** |
| 3 | Type a word, press enter | It is sent |
| 4 | Compose four lines before sending | All four are on screen at once |
| 7 | Paste four lines from an editor | **One** message, not four |
| 8 | Same paste | All four lines, in the order they were pasted |
| 9 | Paste something long | No turn starts until the paste has finished arriving |
| 10 | Paste text whose last line has no trailing newline | Still one complete message |
| 12 | Type `hello`, enter | Exactly as it behaved before any of this |
| 18 | Compose `a`, ctrl+enter, ctrl+enter, `b` | The blank line between them survives into what the model sees |
| 24 | While composing | It is possible to tell how many lines are in hand |
| 25 | Compose two lines, then press ctrl+c | Nothing is sent; the prompt comes back empty |
| 26 | Immediately after that | The session is still alive — type another message and it works |
| 27 | After that, ask the model what you just said | It knows nothing of the abandoned lines |

**AC 27 had a test and the test was vacuous.** It composed one message and asserted that the
string `"throw this away"` was absent from what reached the model — a string nothing ever
typed. It passed for every implementation there is, including one that sent the abandoned
buffer. Abandoning happens inside `compose`'s ctrl+c binding and nothing leaves the reader, so
the criterion is true *and* invisible from outside a session. It is here rather than in a test
that cannot fail.

## AC 6, and the decision made about it

> On a terminal that cannot report ctrl+enter separately from enter, the user is still able to
> send a message of more than one line, and is told how.

**Decided in cycle 10: real, unimplemented, and unverifiable on the only console axiom has
run on.** It stays in the issue and it sits here, unticked, until someone can actually see it.

- `assumption.md` records that AC 6 was written by the agent rather than asked for.
- Kaushik's console *does* report ctrl+enter separately — measured, `0a` against `0d` — so the
  situation the criterion describes has never occurred here.
- It cannot be tested either way: a fallback lives in the key handling, and building a
  `PromptSession` is prohibited.

**Not struck**, and that is the deliberate half. Striking it means renumbering thirty
criteria, and cycle 7 spent a whole cycle repairing eleven citations after the last
renumbering. An unticked row costs nothing; a renumbering costs a day.

**Revisit when** axiom first runs on a terminal where ctrl+enter arrives as a plain `\r` —
most Linux and macOS terminals. At that point it is an observed problem with a real reporter,
and it gets built from evidence rather than from a guess.

## Two things found while proving the rest, and neither is #80's

- **[#83](https://github.com/kaushikhazra/axiom/issues/83)** — scheduling anything silently
  switches multi-line input off. `read_line`'s timed path never consults the composer, so a
  user with a job set gets the old single-line reader and is told nothing.
- **AC 21 needed nothing built.** #42's refusal already names what is over and by how much and
  rolls the message out of the history, and a paste is a long line like any other. It is
  proved against both breaks that matter: the quiet truncation, and the refusal ending the
  session.

## The rule that outlives this file

Do not write another test that constructs a `PromptSession`, a `create_pipe_input`, or a key
processor. `tests/test_multiline.py`'s docstring says the same thing, and so does
`tests/conftest.py`, because the next session will not remember the crash.

---

## What happened - 2026-09-03

**Driven by hand by Kaushik, on `master` with #76, #80 and #81 all merged.** The pass opened
by failing its central criterion, which is the best thing it could have done.

### AC 2 failed on the first row that needed a second line

**Ctrl+enter sent the message.** Traced, fixed and merged the same sitting - see
`fix(#80): ctrl+enter is a bare c-j on every console axiom will meet`.

prompt_toolkit has two Windows readers and `Win32Input.__init__` picks between them on
`_is_win_vt100_input_enabled()`, which asks only whether the console *accepts*
`ENABLE_VIRTUAL_TERMINAL_INPUT` - true on every modern console, conhost included:

| reader | ctrl+enter arrives as |
|---|---|
| `ConsoleInputReader` | `escape, c-j` - ctrl state set, so Escape is prefixed |
| `Vt100ConsoleInputReader` | `c-j` - a bare line feed, nothing to prefix |

Only the pair was bound. The bare key matched nothing, fell through to prompt_toolkit's own
`c-j` default - `feed(KeyPress(ControlM, "\r"), first=True)` - and reached the send binding.

**The console was never the problem.** `tests/whatkey.py`, written to settle it, reports
`ControlJ` for ctrl+enter against `ControlM` for enter. This terminal separates them perfectly
well; axiom was listening for the wrong shape. **AC 6 is untouched** and stays exactly as
cycle 10 left it.

**Nothing about the 21 test-proved criteria is in question.** They proved what axiom does
*given* the key pair, and `compose`'s own docstring said so - "not that this console delivers
it. That second half is the manual pass's, and it is why AC 2 and AC 3 stay off the proved
list." It was right, and the thing it warned about is what happened.

### The rows

| AC | Verdict | |
|---|---|---|
| 1 | pass | three lines, one message - the model read "three words", not three turns |
| 2 | pass | after the fix |
| 3 | pass | enter sends |
| 4 | pass | every line on screen together |
| 5 | pass | said once, above the prompt, and not again on the next message |
| 12 | pass | a one-line message behaves as it always did, with `c-j` newly bound |
| 18 | pass | a blank line survived into the fence the model echoed back - **and so did one from an earlier message**, which had to travel through the conversation history to get there |
| 23 | pass | the grey `…` marks a line as still being written |
| 24 | pass | by "see them all", which is the criterion's other half |
| 7 | pass | a fourteen-line paste arrived as one `>` and thirteen `…` |
| 8 | pass | every line in order; the model quoted four of them back by content |
| 9 | pass | no turn began while the paste was arriving |
| 25 | pass | two composed lines, ctrl+c - no turn, no reply, and the prompt came back empty |
| 26 | pass | the next message answered normally, straight after |
| 27 | pass | **the first real check this criterion has had.** Asked for its previous message, the model named the one typed *after* the abandon. The abandoned buffer never reached it |
| 10 | pass | a paste cut short of its trailing newline is a complete message, and enter sends it |

**AC 19 and AC 11 were seen too**, though both are on the proved list: a message ending on a
blank line produced no empty turn after it, and a pasted `/etc/pipeline/config.yaml` sat in the
message as text rather than being read as a command.

**A pasted blank line takes a different path from a typed one**, and both were seen to survive
- the typed one in the fence the model echoed back, the pasted one on screen inside the
traceback. Nothing tested either.

**AC 27's vacuous test is answered.** It asserted that `"throw this away"` was absent from what
reached the model - a string nothing in the test ever typed, so it passed for every
implementation there is, including one that sent the abandoned buffer. Driven by hand it holds:
the model, asked for its previous message, named the one typed after the abandon.

### Where it ends

**All fourteen rows pass**, and four criteria on the *proved* list - AC 5, AC 11, AC 19 and
AC 23 - were seen on a screen for the first time along the way.

**AC 6 stands unticked, exactly as cycle 10 left it.** The evidence for keeping it there is
stronger now rather than weaker: `tests/whatkey.py` reports `ControlJ` for ctrl+enter against
`ControlM` for enter, so this console separates them and the situation the criterion describes
has still never occurred here. Revisit when axiom first runs somewhere it does.

**One defect, found on the first row that needed a second line, and it was the issue's central
criterion.** A pass that had been run before the merge would have found the same thing; a pass
that was never run would have shipped it. The 21 test-proved criteria were all sound - what
failed was the one thing the tests had said in writing they could not reach.

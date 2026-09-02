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

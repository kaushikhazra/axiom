# #80 — the manual pass

The automated tests that pressed keys are gone (commit `32daf51`). They built a real
`prompt_toolkit` session, and `_say_how_to_send` reaches the *real* console through
`run_in_terminal` rather than the `DummyOutput` the test supplied — which is how a
pytest run escaped into the session that launched it and took the machine down twice.

So the key presses are checked here, by hand, at a real terminal. Everything below was
either proved by a test that has since been deleted or was never proved at all.

Run it as `axiom` in a normal terminal — not through a pipe, not inside a harness.

## Still covered by a test — do not re-check by hand

AC 5, 11, 13, 19, 20, 23, 27, 30, 31, 33, 34, 35, 36.

## What a person has to look at

| AC | What to do | What should happen |
|---|---|---|
| 1 | Type `first`, ctrl+enter, `second`, enter | One message arrives with both lines |
| 2 | Type a word, press ctrl+enter | The cursor drops to a new line; **nothing is sent** |
| 3 | Type a word, press enter | It is sent |
| 4 | Compose four lines before sending | All four are on screen at once |
| 6 | If ctrl+enter does nothing on this terminal | axiom still offers a way to write a second line, and says what it is |
| 7 | Paste four lines from an editor | **One** message, not four |
| 8 | Same paste | All four lines, in the order they were pasted |
| 9 | Paste something long | No turn starts until the paste has finished arriving |
| 10 | Paste text whose last line has no trailing newline | Still one complete message |
| 12 | Type `hello`, enter | Exactly as it behaved before any of this |
| 18 | Compose `a`, ctrl+enter, ctrl+enter, `b` | The blank line between them survives into what the model sees |
| 24 | While composing | It is possible to tell how many lines are in hand |
| 25 | Compose two lines, then abandon (ctrl+c) | Nothing is sent; the prompt comes back empty |
| 26 | Immediately after that | The session is still alive — type another message and it works |

## Not built, so nothing to check

**AC 21** — an oversized paste refused with a reason. Never started. This is the one with
the trap in it: a half-built refusal that silently shortens is worse than no refusal,
which is why #42 exists. Leave it whole or leave it alone.

**AC 15, 16, 17, 22, 28, 29, 32** — believed true and untested. 15–17 are what reaches the
model and what it costs; 28–29 are "nothing to configure", whose proof is that a fresh run
works with no flag; 22 is a line wider than the window arriving in full; 32 is a scheduled
prompt taking a path that never touches the reader. None needs a key press, so any of them
could still be settled by a test — just not one that builds a session.

## The rule that outlives this file

Do not write another test that constructs a `PromptSession`, a `create_pipe_input`, or a
key processor. `tests/test_multiline.py`'s docstring says the same thing, and so does
`tests/conftest.py`, because the next session will not remember the crash.

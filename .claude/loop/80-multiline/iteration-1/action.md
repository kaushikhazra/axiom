# Action — cycle 5

**Paste.** AC 7, 8, 9, 10 — the hardest thing in the issue, and the reason #80 is filed
as a bug rather than as a missing feature.

## What is actually broken, measured

Three lines pasted into a running axiom, before any of this:

    >
    Please provide the rest of your request.
    >
    Please provide the full text or instructions you would like me to work with.
    >
    Please provide the full text or instructions you would like me to work with.

Three turns, three requests paid for, three useless answers, and the message the user meant
never assembled. **AC 9 is the criterion that fixes it**: nothing is sent while a paste is
still arriving.

## Do these in order

1. **Find out what the terminal actually sends.** A paste is a burst of lines with no
   keypress between them, and terminals bracket it - `\x1b[200~` before and `\x1b[201~`
   after - when the program asks for that mode. prompt_toolkit supports bracketed paste and
   delivers it as a single `Keys.BracketedPaste` event with the whole text.
   **Check whether it is on by default in a `PromptSession`** before writing anything: if it
   is, AC 7, 8 and 9 may already hold, and the work is proving it rather than building it.

2. **Prove AC 9 the hard way.** `create_pipe_input` can send a bracketed-paste sequence, so
   a test can deliver a real paste without a terminal. Assert the whole paste is **one**
   return value - and that no line of it was sent on its own, which is the failure being
   fixed.

3. **AC 10 — a pasted line beginning with `/` is text, not a command.** The reader returns
   text either way, so this criterion lives above it, in the chat loop's command matching.
   Look at where `/exit` is recognised: it must match a *whole message*, not the first line
   of one. This is the criterion that pulls against AC 13, where a typed `/exit` must still
   work.

4. **AC 8 — order preserved**, which sounds free and is the cheapest place for an
   off-by-one to hide when lines are reassembled.

## Watch for

- **The failure mode is a partial send, and it does not look like a failure.** A test that
  asserts "the paste came back" passes for an implementation that sent line one and returned
  lines two and three. Assert the *whole* paste and assert the turn count.
- **AC 20 is nearby and not this cycle's**: an oversized paste refused with a reason. Note
  it if the paste path makes it easy, but do not do it instead of AC 9.

## Do not

- Regenerate the baseline.
- Let a break hang. Every pipe input is closed in the helper; keep it that way.

## Record

`logs/cycle-5.md`, per `observe.md`. Criteria out of 36, suite count and wall-clock, the
baseline's state, and the running list of what only a person can confirm — a real paste from
a real terminal is on it.

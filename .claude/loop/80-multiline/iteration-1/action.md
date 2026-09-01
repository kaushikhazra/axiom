# Action — cycle 6

**Abandoning, and the guards.** AC 24, 25, 26, then 32 to 36.

The feature works. What is left is what happens when the user changes their mind, and
proving that nothing else moved.

## Do these in order

1. **AC 24, 25, 26 — abandoning a part-composed message.**
   - ctrl+c with a half-written message clears it and returns to an empty prompt.
   - It does **not** end the session, which is the trap: `read_line` currently treats
     `KeyboardInterrupt` at the prompt as "leave", and that was right when a prompt held
     one line and nothing was in progress. With a message part-written it is now wrong -
     the user meant "not that", not "goodbye".
   - The conversation is exactly as it was: nothing sent, nothing in history.
   - **AC 36 is the other half and pulls the other way**: leaving with a message
     part-composed must still leave. Ctrl-d at an *empty* prompt still exits. Both, or
     neither counts.

2. **The unchanged set — AC 32, 33, 34, 35.** Guards on behaviour that ships.
   - AC 33 has its before: `.tmp/before-80.txt`, a piped single-line session captured in
     cycle 2 before any of this landed. Compare and account for every difference. The one
     already seen is the context window, which Ollama reports differently run to run.
   - AC 34 and AC 35 are the exits, and they are cheap.

3. **AC 21 if there is room — an oversized paste refused with a reason, never silently
   shortened.** Leave it rather than rush it: **#42 exists because of a truncation on the
   other side of this conversation**, and a half-built version of this is worse than none.

## Watch for

- **AC 25 is the one that will be got wrong.** "Does not end the session" is easy to
  satisfy by catching the interrupt somewhere that also swallows a real ctrl+c at an idle
  prompt. Prove both: abandoning does not exit, and ctrl+c at an *empty* prompt still does
  what it always did.
- Every criterion here is about a key press. A pipe input proves the reader; **what a person
  sees when they press ctrl+c is on the manual pass's list** and should be added to it.

## Do not

- Regenerate the baseline. Eleven cycles.
- Use a heredoc for anything containing a backslash escape. Four times this session.

## Record

`logs/cycle-6.md`, per `observe.md`. Criteria out of 36, suite count and wall-clock, the
baseline's state, and the running list of what only a person can confirm.

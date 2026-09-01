# Action — cycle 3

**The reader.** AC 1 to 5, and AC 33.

The confinement is proved and the hook exists, so the reader can be built behind both.

## Do these in order

1. **A real composing reader**, behind `use_compose`'s seam, using `prompt_toolkit`:

       enter        c-m            accept the message
       ctrl+enter   escape, c-j    insert a newline

   **Not `"c-enter"`** — there is no such key. On Windows ctrl+enter arrives as `\x0a`
   with the control state set, and prompt_toolkit converts that to escape-then-ControlJ,
   the VT100 convention for a meta-modified key. The mapping is quoted in `logs/cycle-1.md`
   with the source it was read from.

2. **AC 33 has its before.** `.tmp/before-80.txt` holds a piped single-line session captured
   before any of this landed. Compare against it and account for any difference — the one
   already seen is the context window, which Ollama reports differently run to run and is
   not axiom's doing.

3. **Wire the reader in** so a real terminal session uses it, with the plain path untouched.

## Prove

Every criterion here is reachable by driving the reader with key presses that
`prompt_toolkit` can be fed — its `PipeInput` exists for exactly this and does not need a
terminal. **That proves the reader, not the terminal**, which is a distinction the log must
keep making: a test that feeds `escape, c-j` proves axiom does the right thing with that
key, not that this console delivers it.

Break each one. On the measured rate from #77, roughly one break in four is aimed at the
code rather than at the criterion and proves nothing.

**AC 33 is the one to be careful with.** A single-line session must produce exactly the
bytes it produces today, and the reader is now in that path at a terminal. The failure mode
is subtle: an extra newline, a moved cursor, a prompt drawn twice.

## Do not

- Touch paste handling. That is cycle 4, and AC 9 is the hardest criterion in the issue.
- Regenerate the baseline. Two issues and eight cycles without it moving.

## Also

`uv.lock` is still owed — it does not list `prompt_toolkit`. Run `uv lock` if no axiom
session is holding `.venv/Scripts/axiom.exe`; if one still is, carry the note forward rather
than dropping it.

## Record

`logs/cycle-3.md`, per `observe.md`. Criteria out of 36, suite count and wall-clock, the
baseline's state, and any addition to the list of what only a person can confirm.

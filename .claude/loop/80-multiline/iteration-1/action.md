# Action — cycle 7

**The boundaries.** AC 19, 20, 21, 36 — then 6, 11, 14, 15, 16, 17, 27, 28, 29, 31.

Twenty of thirty-six hold. What is left is mostly edges, and one of them has a real trap.

## Before anything else

**Check `git diff` for a break left behind.** A break-proof that is killed - a timeout, a
SIGTERM, a machine going down - never runs its `finally`, and leaves the break in the real
file. That has happened three times in this loop. The symptom is a red suite for a reason
that has nothing to do with the code.

## Do these in order

1. **AC 19 and AC 20 — trailing and empty.**
   - Blank lines at the end of a message do not become a message of their own.
   - A message that is *only* blank lines sends nothing and leaves the prompt where it is.
   - `read_line` already calls `.strip()` on what the composer returns, so part of this may
     hold already. **Check before building**, and if it holds, prove it rather than counting
     it.

2. **AC 36 — leaving with a message part-composed exits rather than sending it.**
   Ctrl-d with text in the buffer. prompt_toolkit raises `EOFError`, which `read_line`
   already turns into "leave". The question is whether the half-written text goes anywhere,
   and it must not.

3. **AC 21 — an oversized paste is refused with a reason, never silently shortened.**
   **This is the trap.** #42 exists because of a truncation on the other side of this
   conversation, and a half-built version of this is worse than none. The refusal has to
   say what happened and roughly by how much, the way `note_skill_too_large` does. If it
   cannot be done properly in one cycle, do the cheaper criteria and leave this whole.

4. **The remainder** — 6, 11, 14, 15, 16, 17, 27, 28, 29, 31 — are mostly already true and
   need proving rather than building. AC 31 is the schedule path: a scheduled prompt is a
   string that never touches the reader, so it should be untouched, and one test says so.

## Watch for

- **AC 27, 28, 29 are the "nothing to configure" group.** They are easy to claim and the
  proof is that a fresh run works without a flag, not that a flag exists.
- **AC 14 pulls against AC 10 again** - a command is never the first line of a longer
  message. That is the guard added in cycle 5; it needs its own citation and break here
  rather than riding on AC 10's.

## Do not

- Regenerate the baseline. Twelve cycles.
- Use a heredoc for anything containing a backslash escape. Four times this session.
- Leave a break in the file. Check `git diff` before finishing, not just before starting.

## Record

`logs/cycle-7.md`, per `observe.md`. Criteria out of 36, suite count and wall-clock, the
baseline's state, and the running list of what only a person can confirm.

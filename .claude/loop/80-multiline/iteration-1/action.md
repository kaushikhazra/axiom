# Action — cycle 8

**The five that are nearly true, then the one that is not.**

## Before anything else, two checks

1. **`git status`** — a break-proof killed mid-run leaves the break in the file. Three
   times in this loop.
2. **The citation grep.** Cycle 7 found eleven mis-numbered citations, and the count had
   been wrong for four cycles because of it:

       grep -rhoE "#80 AC [0-9]+" tests/*.py src/axiom/*.py | grep -oE "[0-9]+" | sort -n -u

   Diff against `gh issue view 80`. Do this at the **start**, not only at the end.

## Do these in order

1. **AC 19, AC 20 — trailing and empty.** Measured in cycle 7 and both already hold, but
   at the `read_line` level rather than in `compose`: the composer returns `'hello\n\n'`
   and `read_line` strips it. **Prove them where they are true**, which means through
   `read_line` or `main`, not through `compose` — a test at the wrong level would pass for
   the wrong reason.

2. **AC 36 — leaving with a message part-composed.** Ctrl-d with text in the buffer raises
   `EOFError`, which `read_line` already turns into "leave". Measured; needs a test and a
   break saying the half-written text goes nowhere.

3. **AC 32 — a scheduled prompt is unaffected.** A scheduled prompt is a string that never
   touches the reader, so this should be true already. One test, and a break that would
   catch a composer creeping into `_next_line`'s path.

4. **AC 22 — a message whose lines are wider than the window is sent in full.** The
   *reader's* side, not the renderer's: a pasted line of 500 characters arrives whole. #72
   owns what happens when it is drawn; this owns what happens when it is read.

5. **AC 21 — an oversized paste refused with a reason, never silently shortened.**
   **The trap.** #42 exists because of a truncation on the other side of this conversation.
   The refusal must say what happened and roughly by how much, as `note_skill_too_large`
   does. **If it will not fit in this cycle, leave it whole** — a half-built refusal is
   worse than none, because it looks like a feature.

## Still not started after that

AC 6, 15, 16, 17, 28, 29. Mostly "already true, needs proving": 15 to 17 are what reaches
the model and what it costs, and 28 to 29 are the nothing-to-configure group, whose proof is
that a fresh run works without a flag.

## Do not

- Regenerate the baseline. Thirteen cycles.
- Use a heredoc for anything containing a backslash escape.
- Leave a break in the file. Check `git diff` before finishing.

## Record

`logs/cycle-8.md`, per `observe.md`.

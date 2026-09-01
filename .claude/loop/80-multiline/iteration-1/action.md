# Action — cycle 9

**The count changed under you. Establish it before building anything.**

Nineteen tests were deleted between cycle 8 and this one — every test that built a real
`prompt_toolkit` session, because running them crashed Kaushik's machine twice. See `loop.md`
and `assumption.md`. Thirteen criteria left the tested set with them and are now a person's:
AC 1, 2, 3, 4, 7, 8, 9, 10, 12, 18, 24, 25, 26.

**This loop's target is the 23 a test can still reach**, listed in `loop.md`.

## Before anything else, three checks

1. **`git status`** — a break-proof killed mid-run leaves the break in the file. Four times
   in this loop.
2. **The citation grep**, at the start rather than the end:

       grep -rhoE "#80 AC [0-9]+" tests/*.py | grep -oE "[0-9]+" | sort -n -u

   Ignore the `80` — that is the issue number in `#80`, not a criterion. Diff the rest
   against `gh issue view 80`.
3. **`grep -rn "PromptSession\|create_pipe_input\|KeyBindings" tests/`** — must return
   nothing. If it returns something, a cycle reintroduced the crash; delete it first and say
   so in the log before doing anything else.

## Then re-measure, and do it honestly

Cycle 7's bucket 1 was 18 of 36. It is smaller now, and **smaller is the correct answer** —
those criteria were proved by tests that no longer exist. Report the new number **out of 23**,
with the thirteen manual ones listed separately and never folded in. A cycle that reports 36
of 36 because it counted the manual list has said "verified" about something nobody has looked
at, which is worse than the mis-numbering cycle 7 found.

## Do these in order

1. **AC 22 — a line wider than the window is sent in full.** Its test was one of the nineteen,
   and it did not need to be: the composer is reachable through `use_compose`, so a substitute
   returning a 500-character line proves the reader passes it on whole. Rebuild it at that
   level. #72 owns what happens when it is *drawn*; this owns what happens when it is *read*.

2. **AC 32 — a scheduled prompt is unaffected.** A scheduled prompt is a string that never
   touches the reader. Should be true already; needs one test and a break that would catch a
   composer creeping into `_next_line`'s path.

3. **AC 15, 16, 17 — what reaches the model and what it costs.** One message with its line
   breaks intact, one entry in the conversation, one request. All three are assertions about
   `stub.streamed`, which `sent_to` in `tests/test_multiline.py` already returns. Cheap, and
   they are the criteria that say the bug is actually fixed.

4. **AC 28, 29 — nothing to configure.** The proof is that a fresh run works with no flag and
   that no setting exists which makes a single-line message behave differently from today.
   Attack 29 rather than confirming it: grep for anything that gates the composer, and if a
   switch exists, that criterion is not met.

5. **AC 14 — a command is never the first line of a longer message.** Cycle 7 found this
   riding on a test that cited AC 10. Give it a test of its own and a break that separates it
   from AC 11.

6. **AC 21 — an oversized paste refused with a reason, never silently shortened.**
   **The trap, still unbuilt.** #42 exists because of a truncation on the other side of this
   conversation. The refusal must say what happened and roughly by how much, the way
   `note_skill_too_large` does. **If it will not fit in this cycle, leave it whole** — a
   half-built refusal is worse than none, because it looks like a feature. Do not start it
   after 03:15.

7. **AC 6 — the terminal that cannot report ctrl+enter.** `assumption.md` says this one was
   written by the agent rather than asked for, and is the cheapest to strike if it fights the
   implementation. It now also cannot be tested without a session. **Decide it this cycle**:
   either it is real and moves to `manual-pass.md` with the other thirteen, or it is struck
   from the issue with a comment saying why. Record the decision and the reasoning in the log.
   Do not carry it another cycle undecided.

## Do not

- **Write a test that builds a `PromptSession`, a `create_pipe_input`, or a key processor.**
  This is the prohibition in `assumption.md` and it outranks any criterion.
- Attempt a manual criterion, or wait for one.
- Regenerate the baseline. Fourteen cycles.
- Use a heredoc for anything containing a backslash escape.
- Leave a break in the file. Check `git diff` before finishing.
- Merge. #80 leaves this loop committed and unmerged, pending Kaushik's manual pass.

## Record

`logs/cycle-9.md`, per `observe.md`. Then, if the goal check in `loop.md` says done, follow
the queue's **Handing over** procedure — mark row 18 done, scaffold row 19
(`76-indented-code`), mark it running, and **do not delete the cron**.

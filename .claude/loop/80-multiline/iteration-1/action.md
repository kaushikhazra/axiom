# Action — cycle 10

**AC 21, and then decide AC 6.** Those are the last two things this loop owns.

Cycle 9 left **19 of the 23 a test can reach**. Bucket 2 holds AC 27 and AC 35; bucket 3
holds AC 21 alone; AC 6 is undecided. The thirteen on `manual-pass.md` are not this loop's and
are never counted.

## Before anything else, three checks

1. **`git status`** — a break-proof killed mid-run leaves the break in the file. Four times.
2. **The citation grep, with the wider pattern.** Cycle 9 found the narrow one blind: it only
   ever sees the first criterion of a phrase, so `"#80 AC 23, and AC 4 and AC 24 with it"`
   reported as citing AC 23 alone, and two false claims hid behind that for two cycles.

       grep -rhoE "AC [0-9]+" tests/test_multiline.py | grep -oE "[0-9]+" | sort -n -u

   Every `AC` in that file is #80's, so the prefix is not needed and costs coverage. Diff
   against `gh issue view 80`.
3. **`grep -rn "PromptSession\|create_pipe_input\|KeyBindings" tests/`** — must return only the
   two docstrings that forbid them. Anything else is the crash coming back; delete it and say
   so before doing anything else.

## 1 — AC 21, the oversized paste

> A paste too large for the model's window is refused with a reason, and is never silently
> shortened.

**The trap, and it is the reason #42 exists.** A truncation on the other side of this
conversation is what that issue was filed for. A refusal that shortens quietly, or that says
"too large" without saying how much too large, has met the words and not the criterion.

What exists to copy rather than invent:

- `note_skill_too_large` in `terminal.py` — the shape of a refusal that says what happened and
  roughly by how much. #75 settled this argument already.
- `too_large` and `estimated_tokens` — and the queue's Standing warns about exactly these:
  *a number is only as good as the function it came from*. One divides by four and the other
  by three. Measure, do not assume.

Where it goes: `read_line`, on the composed string, before it is returned. Not in `compose`,
because a piped run can also deliver an enormous line and the refusal belongs to both paths.

**Two tests and two breaks**, through the `use_compose` hook:

- an oversized message is refused, the refusal names the size and the limit, and
  **`stub.streamed` is empty** — nothing reached the model;
- the message is **not** shortened and sent — the break to watch is a `[:limit]` that returns
  a truncated string, which must go red on an assertion that the model got nothing at all
  rather than got less.

**If it will not fit, leave it whole.** A half-built refusal looks like a feature and is worse
than none. Say so in the log and hand over; AC 21 is one criterion and it is not worth
shipping a silent truncation to close it.

## 2 — AC 6, decided this cycle

> On a terminal that cannot report ctrl+enter separately from enter, the user is still able to
> send a message of more than one line, and is told how.

`assumption.md`: it was written by the agent rather than asked for, and is the cheapest
criterion to strike if it fights the implementation. It now also **cannot be tested without a
session**, which is prohibited. So it is one of two things and not a third:

- **real** — it moves to `manual-pass.md` with the other thirteen, and the manual pass gains a
  row saying what a user on such a terminal should see;
- **struck** — it comes out of the issue with a comment saying why.

Decide, record the reasoning in the log under a heading that says it was a decision, and carry
it into the handover. **Do not leave it undecided a third cycle.**

## 3 — If there is time: AC 27 and AC 35

Both are in bucket 2 — tested, never break-proven. Cheap. AC 27 is "an interrupted compose
leaves the conversation exactly as it was"; AC 35 is end of input at an empty prompt exiting
with today's status code.

## Do not

- **Write a test that builds a `PromptSession`, a `create_pipe_input`, or a key processor.**
  The prohibition in `assumption.md` outranks any criterion, AC 6 and AC 21 included.
- Attempt a manual criterion, or wait for one.
- Regenerate the baseline. Fifteen cycles.
- Use a heredoc for anything containing a backslash escape.
- Leave a break in the file. Check `git diff` before finishing.
- Merge.

## Then hand over

With AC 21 settled either way and AC 6 decided, this row is done as far as the queue is
concerned — bucket 2 is two cheap proofs and bucket 3 is empty or explained. Follow the queue's
**Handing over**: mark row 18 done with the split stated as **N by test, 13 by Kaushik** and
never as a total, scaffold row 19 (`76-indented-code`), mark it running, and **do not delete
the cron**.

## Record

`logs/cycle-10.md`, per `observe.md`.

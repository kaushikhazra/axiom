# Cycle 5 — the tool summary, the prompt, and the guards

2026-09-01, 17:07 +0530. Branch `feature/77-look`. Committed.

## The measurement

**Criteria demonstrably met: 34 of 37.** Moved by 10.

| bucket | count | criteria |
|---|---|---|
| **1 — met, proved by a break** | **34** | 1–26, 30–37 |
| 3 — not started | 3 | **27, 28, 29** — the voice |

## The suite

    861 passed, 1 deselected, 80.12s     entering
    870 passed, 1 deselected, 89.54s     leaving

Arithmetic: 861 + 9 = 870.

**`tests/baseline/transcript.txt` is untouched. Five cycles, zero lines.**

The wall clock is up 9s and it is worth naming rather than passing over: this
cycle added nine tests, four of which drive a whole `main()` run. That is work
being done, not a slowdown - the opposite of the pattern `observe.md` warns
about, where a *faster* suite means a test doing less.

## What the turn looks like now

Four calls used to cost twelve lines of bookkeeping around one paragraph of
answer. A turn now shows nothing per call, a transient line while each one runs,
and one grey line when the turn finishes:

    ·  4 tools, 2 failed

The transient line is taken back with `\r` and erase-to-end-of-line - the pair
`Rendered` already uses to replace an echoed line with a styled one. Machinery
axiom had, not machinery it needed.

The summary lands in `end_turn`, not at the end of the tool rounds. A turn can go
model → tool → model → tool, and AC 24 asks for one line when the **turn**
finishes rather than one per round. The counters reset there too, on every route
out including the failure path — a turn that ended badly would otherwise spill
its count into the next one.

**A divergence from the mock, stated so it can be corrected in a word.**
`.tmp/mock_quiet_turn.py` drew the summary *above* the answer. It is now *below*,
because `end_turn` is the one place every route out of a turn passes through and
AC 24's wording is "when a turn that called tools finishes". Putting it above
would mean emitting it from the tool loop, which fires once per round.

## A bug of mine, found by a test rather than by review

`show_facts` was gated on `sys.stdout.isatty()` alone, so **`--no-render` still
drew the panel.** AC 32's test caught it on its first run.

`use_rendering` already states the rule and states it well:

> Off takes the same path a redirected run takes, rather than a quieter
> rendering - so "off" is the behaviour the golden transcript already records,
> and there is one plain path rather than two that have to be kept identical.

A panel under `--no-render` would have made "off" mean two different things in
one session. Every path added by #77 is now gated on `_rendering` **and** the
terminal. Cycle 4 got this wrong and the suite was green, because nothing tested
`--no-render` against the panel until this cycle wrote AC 32's guard.

## A gap in the instrument that had been hiding a cleared screen

`tests/screen.py` read **every** `J` as "erase from the cursor down":

    elif letter in ("K", "J"):
        self._truncate(to_end_of_screen=letter == "J")

`\x1b[J` and `\x1b[0J` do mean that. **`\x1b[2J` erases the whole screen whatever
the cursor is doing**, and `\x1b[3J` takes the scrollback with it. Reading the
parameter as irrelevant left everything above the cursor standing, so a screen
that had been cleared still showed the line that had been on it.

That is not academic: **cycle 4 measured AC 8 against it.** Those assertions were
made on the raw byte stream and so were unaffected, but the first test this cycle
that asked "what is left on the screen" got a wrong answer and was right to.

Fixed to honour the parameter. The screen model is now correct about the one
escape #77 introduced.

## A test that proved a call happened by a line #77 deleted

`test_a_reply_that_turns_out_to_be_a_call_never_reaches_the_renderer` asserted
`"read_file(path=x)" in printed` as its evidence the call was made. AC 22 removes
that line.

Deleting the assertion would have left the test passing for a build that **never
made the call at all** - which is the failure the test exists to exclude, since
"the call text never reached the renderer" is trivially true if there was no call.
Re-pointed at the summary line instead.

Its AC 26 half then failed for the opposite reason, and this is the shape worth
remembering:

> The transient line is **written and then taken back**. Its bytes are in the
> stream whatever the user ends up seeing. Asserting `"read_file" not in printed`
> fails on correct behaviour; asserting only that the summary is present passes on
> a renderer that never erased anything. **Only a screen tells the two apart.**

`action.md` predicted exactly this and it still took a red test to act on it.

## Breaks

Ten, all red once each was aimed at the criterion rather than at the code.

| criterion | break |
|---|---|
| AC 22 | a line is printed for every call, as before |
| AC 23 | nothing is shown while a tool runs |
| AC 24 | the summary never counts more than one |
| AC 25 | a turn with no tools is summarised anyway |
| AC 26 | the tool's output is printed at a terminal too |
| AC 30 | the prompt carries no accent |
| AC 32 | `--no-render` still draws the panel |
| AC 35 | a bare run gains three lines it did not have |
| AC 36 | a failed tool is not counted |
| AC 37 | an unreachable host is reported differently |

AC 26's first break stayed green: it removed the erase from `show_tool_result`,
and `end_turn` erases too, so nothing was left behind. The break was wrong rather
than the test — the failure mode is the tool's *output* being printed, not the
transient line surviving. Third cycle in a row that a break needed re-aiming.

## Assumptions changed

None.

## Next

**Three criteria: 27, 28, 29 — the voice.** `VOICE` appears in 44 f-strings in
`terminal.py`, seven of them to stderr. The conversion is mechanical and the
suite plus the baseline will catch a slip, but it is a wide diff and it was kept
out of this cycle deliberately rather than bolted on: a wide mechanical change and
a set of new behaviours in one commit is a diff nobody reads twice.

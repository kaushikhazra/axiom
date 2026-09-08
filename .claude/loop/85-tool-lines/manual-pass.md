# #85 — the manual pass

No loop folder and no `iteration-1/`, because #85 never had a loop: it was written,
built and merged in one evening on 2026-09-03 after #74's pass found what it is for.
This file is the pass, and it lives here so a fresh session finds it next to #74's.

**The tests cite ten of thirty criteria.** Searched across the whole suite, the only
#85 numbers any test claims are:

    1, 2, 7, 10, 11, 12, 14, 16, 17, 20

Twenty are cited by nothing. Some of those are safe by other means — AC 24, 25 and 26
are what `tests/baseline/transcript.txt` is for, and it has not moved. The rest are
uncited because they are about **what a thing looks like**, and #85 changed nothing
except what a thing looks like.

## Setup

    cd C:\Projects\.tmp\axiom-manual
    uv run --project C:/Projects/axiom axiom --model qwen2.5:7b --no-mcp

**`--project`, not `--directory`.** `--directory` moves the working directory into
the repo, which CLAUDE.md's tool-testing rule forbids.

**qwen2.5:7b on purpose.** It answers in seconds where qwen3.5:9b takes one to five
minutes, and none of these rows is about how the model writes. Switch to 9B only for
row 14, where the model's *account* is the thing being looked at.

**Write down your window width before you start** — `mode con` gives it. Rows 5 and
13 both depend on it, and row 13 has a known limit that only bites below about 100
columns.

**The working tree is on `release/74-manual-pass`** (PR #88). Nothing in it touches
#85's drawing; it is the better branch to run because the `run_command` stdin fix
stops `date`-like commands hanging for thirty seconds mid-pass.

## What you are looking at

    ·  run_command(command=ping -n 8 127.0.0.1)
    ·  Reply from 127.0.0.1: bytes=32 time<1ms TTL=128
    ·  Reply from 127.0.0.1: bytes=32 time<1ms TTL=128
    ·  … 9 more lines

`·` is `TOOL_MARK`, `×` is `FAIL_MARK`, both grey, both indented two spaces. Every row
is cut to **one** terminal row with a trailing `…`. A result gets **three** rows and
then a count of what is left. So a tool costs **four lines at most** — one call, three
result.

## The rows

Do them in order. **Leave 13 and 14 until last**: once anything is scheduled the
session takes the timed-read path, and #83 means multi-line composing is gone until
you restart.

| # | AC | Type this | It passes if |
|---|---|---|---|
| 1 | 1 | `Hello. Do not use any tools.` | Nothing tool-shaped anywhere. No `·`, no count |
| 2 | 2, 3, 4 | `Run the command: ping -n 8 127.0.0.1` | **The `·  run_command(command=…)` line appears immediately, and the result rows arrive seconds later.** Watch the gap — this is the only row where AC 3 is visible at all |
| 3 | 5 | `List everything scheduled.` | `·  list_schedules()` — the empty brackets are the criterion |
| 4 | 9 | `Run the command: cd .` | A result line still appears, saying it finished with no output. Silence here would be indistinguishable from a tool that never ran |
| 5 | 6 | `Run the command: echo` then paste 300-odd characters of anything | The call line is **one** row, ending `…`. It must not wrap |
| 6 | 8 | `Run the command: dir C:\Windows\System32` | Three result rows, then `·  … N more lines`. Not a wall of text, and not a silent cut |
| 7 | 10 | `Read the file nope.txt, and also read ai-news-today.md.` | One `×` row and one `·` row **in the same turn**, so you can compare them side by side. See judgement A |
| 8 | 11, 12, 13 | `Run three commands, one after another: echo one, echo two, echo three.` | Three call/result pairs, in that order, none interleaved |
| 9 | 14 | `Read ai-news-today.md, then based on what it says, run echo with the first word of the title.` | **Both** rounds are drawn, not just the first. This is the one #77 got wrong |
| 10 | 15, 16 | look back at rows 6 and 8 | No `·  3 tools` line anywhere — that is what #85 removed. And you can count the tools by counting call lines |
| 11 | 21, 22, 23 | look at any row above | The tool lines are dimmer than the answer, none starts with `axiom:`, and none could be mistaken for the model talking |
| 12 | 28, 29 | `Read the file nope.txt, then tell me a joke.` | The failing tool does not end the turn — the joke still arrives — and the prompt comes back |
| 13 | 18, 19 | `Schedule a repeating prompt, every minute, that says: say TICK` | The identifier **and** `next at … local` are both on screen. **Then set the window to 80 columns and do it again** — the time is cut mid-date and AC 19 fails. See judgement C |
| 14 | 17, 20 | with the job scheduled, on **qwen3.5:9b**: `What did you just schedule, and how long will it last?` | Whatever the model says, the four tool rows above it are still there and still right. If the two disagree, both are on screen — that is AC 20, and it is the whole reason #85 exists |
| 15 | 30 | `/exit`, then `echo %ERRORLEVEL%` | `0`, same as a run that called no tools |

## The three things only you can answer

These are judgements, not criteria. Nothing in the issue settles them and no test can.

**A — is `×` distinct enough from `·` at a glance?** Row 7 puts one of each in the
same turn. They are the same colour and the same indent; only the glyph differs, and
at a small font `·` and `×` are both small and central. The question is not whether
you can tell them apart when looking for it — it is whether a failure **catches your
eye** when you are not.

**B — is four lines per tool too dense?** Row 8 leaves twelve lines for three trivial
`echo` calls. Is that a block you skim past, or one you read? If it is the first, the
visibility #85 bought is spent.

**C — the known limit, and whether it matters.** `schedule_prompt`'s first result row
is the tail the `…` eats, and it was left visible rather than half-fixed because
shortening it means changing `_when()`, which is #74's tested contract.

Measured with `say TICK` as the prompt, so 89 characters of result row:

| window | what survives |
|---|---|
| 100+ | the whole row |
| 90 | `… next at 2026-09-08 22:27…` — the time lives, ` local` is gone |
| **80** | `… next at 2026-0…` — **AC 19 fails outright** |

**The threshold moves with the prompt text**, because the prompt is inside the row —
a job whose prompt is a sentence rather than two words fails at a wider window than
this. Set your terminal to 80 columns for row 13 and you will see it cleanly. The
judgement: is 80 columns a real user's window, or a corner?

## What not to bother with

**AC 24, 25, 26 and 27 are settled and not yours.** Piped output, `--no-render` output
and the golden transcript are byte-for-byte assertions, `tests/baseline/transcript.txt`
has not moved, and the suite is green at 964. Driving them by hand adds nothing.

**AC 7 is really rows 2, 4, 6 and 7 together** — there is no separate thing to do for
"the result appears under the call it answers"; every row above either shows it or
does not.

## Record it here

| # | AC | Verdict | |
|---|---|---|---|
| 1 | 1 | | |
| 2 | 2, 3, 4 | | |
| 3 | 5 | | |
| 4 | 9 | | |
| 5 | 6 | | |
| 6 | 8 | | |
| 7 | 10 | | |
| 8 | 11, 12, 13 | | |
| 9 | 14 | | |
| 10 | 15, 16 | | |
| 11 | 21, 22, 23 | | |
| 12 | 28, 29 | | |
| 13 | 18, 19 | | |
| 14 | 17, 20 | | |
| 15 | 30 | | |

| judgement | | |
|---|---|---|
| A — `×` against `·` | | |
| B — four lines a tool | | |
| C — the narrow window | | |

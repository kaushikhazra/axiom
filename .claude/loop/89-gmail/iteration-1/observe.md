# Observe

## What to record, every cycle

- **The count.** How many of #89's forty criteria are met, and how many are not. A row
  counts as met only when a test or a driven transcript backs it — not when the code
  looks right. Write the number. It is the thing that has to move.
- Where the artifact stands against the goal, and how far that moved from last cycle.
- What moved it. One sentence.
- What is still missing, and whether it can be closed from here at all.
- The suite: passed, deselected, wall clock. All three, every cycle.
- Any assumption that changed.

## Goal check

- **Met** — all forty criteria backed, suite green, wall clock no worse than ~140s. The loop ends.
- **Not met** — report and write the next action.
- **The count did not move for two consecutive cycles** — report the flat result and stop.
  Do not run another variant.

## The criteria that will be got wrong

Named here so a cycle cannot quietly claim them. Each of these is either a negative, a
path a stub will satisfy without proving anything, or a thing the library is assumed to
handle.

| | why it will be got wrong |
|---|---|
| **AC 12** — expired permission renewed without asking | A Testing-mode app expires refresh tokens after 7 days, so the real path is unreachable most of the time. A stub returning a fresh token proves nothing about what axiom does when Google says no. |
| **AC 29, AC 30** — a secret never printed, in whole or in part | A negative over every output path: the tool line #85 draws, the startup failure list, a traceback, a log. Not seeing it once is not evidence. This is a sweep, like `terminal.py`'s escape-sequence sweep — read every place a value can reach the screen. |
| **AC 31** — a message body never written to disk | Same shape. The token cache, a temp file, a debug dump. |
| **AC 37** — no browser when output is redirected | `terminal.py` already has the `isatty` discipline and #74 still found the one function that had missed it. `InstalledAppFlow` opens a browser by default and will not ask. |
| **AC 39** — no listener left behind on exit | `run_local_server()` starts a socket. Assuming the library closes it is exactly the assumption #43 AC 26 and AC 27 exist to disprove. |
| **AC 19** — a body readable whatever encoding it arrived in | Gmail returns base64url, nested multipart, and sometimes HTML with no text part. The happy path is one shape and there are several. |
| **AC 15, AC 16** — revoke from within axiom, effective immediately | There is no command surface for it today. `/model`, `/skill`, `/skills` are all that exist. This is new, not a wiring change. |
| **AC 24, AC 33** — bounded results, quota refusals | Both need a response the happy path never produces, so both will be reasoned about rather than driven. |

## What proves a row

- A criterion about behaviour: a test, named in the log.
- A criterion about what reaches a screen: a transcript or a rendered sample, in `logs/`.
- A criterion that is a negative: the sweep that establishes it, and what was swept.
- A criterion needing a live account: named as owed, and left owed. **A cycle never
  claims a row it could not drive.**

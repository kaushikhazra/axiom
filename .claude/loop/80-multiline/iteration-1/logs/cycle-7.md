# Cycle 7 — the numbers were wrong, and that is the whole cycle

2026-09-01, 23:49 +0530. Branch `feature/80-multiline`. Committed.

## The measurement

**Criteria demonstrably met: 18 of 36.** It was reported as 20 last cycle, and
**that number was wrong** — not because the count slipped, but because some of the
criteria being counted were not the ones being tested.

| bucket | count | criteria |
|---|---|---|
| **1 — met, proved by a break** | **18** | 1, 2, 3, 5, 7, 8, 9, 11, 13, 14, 18, 23, 25, 26, 30, 31, 33, 34 |
| 2 — implemented but not proved | 5 | 4, 10, 12, 24, 27, 35 |
| 3 — not started | 13 | 6, 15, 16, 17, 19, 20, 21, 22, 28, 29, 32, 36 |

**AC 22 and AC 32 leave bucket 1 having never been in it.** AC 22 is "a message whose
lines are wider than the window is sent in full" and AC 32 is "a prompt that arrives from a
schedule is unaffected". Nothing has tested either. They were being reported as met because
tests for *other* criteria carried their numbers.

## What happened

**I renumbered the issue in cycle 0.** AC 6 was inserted - "on a terminal that cannot
report ctrl+enter separately from enter, the user is still able to send a message of more
than one line" - and every criterion after it shifted by one. Tests written before that kept
the old numbers.

    cited     what the test does                    what it really is
    AC 22     a continuation marker                 AC 23
    AC 23     every line stays on screen            AC 24
    AC 10     a pasted /exit is text                AC 11 and AC 14
    AC 24     abandoning clears the message         AC 25
    AC 25     abandoning does not end the session   AC 26
    AC 26     nothing reaches the model             AC 27
    AC 32     --no-render is unchanged              AC 31

Seven citations in the tests, four more in `terminal.py`'s own docstrings.

## How it was caught, and it was not by reading

    grep -rhoE "#80 AC [0-9]+" tests/*.py | sort -n -u

One command. #75 earned this habit and `observe.md` carries it; it has now found something
in **both** issues it has been run on - two criteria covered by accident in #77, and
eleven mis-numbered citations here.

**Reading would not have found it.** Every docstring described the right behaviour and
asserted the right thing. Only the number was wrong, and a number is exactly what a reader
skips over.

## The lesson, and it is not "renumber carefully"

> **An issue is a moving document, and a test citation is a reference into it.** The
> reference has to be re-checked whenever either end moves. There is no version of "be
> careful" that survives inserting a criterion into the middle of a numbered list six
> cycles ago.

The grep belongs in the action file of every cycle that touches an issue's text, not only
at the end. It costs one command and it is the only thing that reads a number as a number
rather than as decoration.

## What that means for the two criteria that fell out

Neither is hard; both simply have not been done.

- **AC 22** — a message whose lines are wider than the window is sent in full. The
  renderer's side of this is #72's whole story. What is untested is the *reader's* side: a
  pasted line of 500 characters must arrive whole.
- **AC 32** — a scheduled prompt is unaffected, however many lines it has. A scheduled
  prompt is a string that never touches the reader, so this should be true already and needs
  one test saying so.

## The suite

    909 passed, 1 deselected, 85.18s     entering
    909 passed, 1 deselected, 86.70s     leaving

No test was added and none removed. **Nothing about the behaviour changed** - only what the
tests claim to be testing. Baseline untouched, thirteen cycles.

## Assumptions changed

None.

## What only a person can confirm — unchanged

Criteria 2, 3, 4, 5, 7, 8, 9, 25.

## Next

AC 19, 20, 22, 32, 36 - four of which are close to true already - and then AC 21, the
oversized paste, which is the one with a real trap in it.

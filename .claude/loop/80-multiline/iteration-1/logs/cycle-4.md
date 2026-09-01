# Cycle 4 — the debts paid, and what composing looks like

2026-09-01, 21:46 +0530. Branch `feature/80-multiline`. Committed.

## The measurement

**Criteria demonstrably met: 8 of 36.** Moved by 6 — the loop's biggest cycle so far,
and half of it was closing what cycle 3 left open.

| bucket | count | criteria |
|---|---|---|
| **1 — met, proved by a break** | **8** | 1, 2, 3, 5, 18, 22, 23, 30 |
| 2 — implemented but not proved | 6 | 4, 12, 13, 14, 31, 32 |
| 3 — not started | 22 | 6–11, 15–17, 19–21, 24–29, 33, 34, 35, 36 |

**AC 4 and AC 23 came together and only one of them counts.** Both are about the lines
being visible while composing; prompt_toolkit keeps them on screen, and the continuation
marker is what AC 22 needed. AC 23 - "can tell how many lines it has, **or** see them all" -
is settled by the second half of its own *or*. AC 4 is the same fact seen from a different
angle and stays unproved, because the test that would prove it is the one only a person can
run: what it looks like.

## The suite

    888 passed, 1 deselected, 84.24s     entering
    891 passed, 1 deselected, 83.93s     leaving

Arithmetic: 888 + 3 = 891. **Baseline untouched**, ten cycles across two issues.

## The three breaks that proved nothing, and what each one turned out to be

Not one story but two, and they are different failures.

**AC 1 and AC 2 were misspelt breaks.** Their search strings contain
`insert_text("\n")`, and a scripted replace turned the backslash-n into a real newline, so
nothing matched. The harness reported "did not apply" and cycle 3 read that correctly rather
than counting them. Rewritten with raw strings, in a file written directly rather than
through a heredoc, both go red immediately.

That is the **third** time this session the backslash rule has cost something. The rule is
not "be careful with escapes" - it is "do not use that tool for that job".

**AC 18 was a wrong break, which is worse, because it looks like a passing test.**
`multiline=False` does not stop `insert_text` putting a newline in the buffer. The criterion
was never violated, the test stayed green, and **the test was right to.** Replaced with a
break that collapses blank lines on the way out, which is what AC 18 actually forbids.

The distinction is worth keeping: a break that does not apply announces itself. **A break
that applies and violates nothing looks exactly like a criterion that holds.**

## What composing looks like now

prompt_toolkit's default continuation is `prompt_width` spaces. It lines the text up and
marks nothing - so a message part way through looks **exactly** like one that has been sent
and answered, which is the single thing AC 22 asks it not to look like.

A marker in the voice's grey now says "still yours, not sent".

It is a named function rather than an inline lambda, and the test is what forced that: it
tried to import `_compose_continuation` and failed. **An inline lambda there would have been
an untested one**, and the criterion would have rested on reading the call site.

## The hint, and why once

Said at the moment a message first grows a second line - the one moment a user has the
question, having just discovered that enter no longer does what it did a second ago. Said
again on the third line it is noise; by the fifth it is in the way of what they are writing.

Two breaks, because the criterion has two halves and either can be lost alone: saying it
every time, and saying only one of "how to send" and "how to add another".

## The lockfile debt is paid

Cycle 2 could not run `uv add` - a live axiom session held `.venv/Scripts/axiom.exe` - so the
package went in with `uv pip install` and `pyproject.toml` was edited by hand, leaving
`uv.lock` disagreeing with it. **`uv lock` ran cleanly this cycle**; prompt_toolkit 3.0.53
and wcwidth 0.8.3 are in the lockfile. A clean checkout now installs what this branch needs.

Carried forward through two cycles' action files rather than remembered, which is the only
reason it did not quietly ship.

## What only a person can confirm — one added

Criteria 2, 3, **4**, 5, 7, 8, 9, 24. AC 4 joins because "the user can see every line"
is a claim about a screen, and the marker's readability is the same kind of claim as #77's
palette: measurable as bytes, judgeable only by eye.

AC 22 and AC 23 leave the list - the marker's *presence* and the lines' *survival* are both
assertable, and are now asserted.

## Assumptions changed

None.

## Next

**Paste.** AC 7, 8, 9, and 10 - the hardest thing in the issue and the reason it is filed as
a bug. Nothing may be sent while a paste is still arriving, and the failure mode is sending
the first line the instant its newline lands.

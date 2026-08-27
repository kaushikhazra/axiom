# Cycle 5 — the second cold read, on cycle 4's fixes

**Three more defects, all in the code cycle 4 wrote to fix the previous four.** None would
have been found by re-reading it.

**Commit** `fix(#60): three more, all in the code cycle 4 wrote to fix the last four`
**Suite** 603 → **614**, green with no Ollama running. **Transcript unchanged.**
**Breaks** 25 → **28**, no survivors — after three were found stale.

This is the answer to whether cycle 4's arrangement — finding four defects and fixing all
four in the same pass — was worth distrusting. It was.

---

## Finding 1 — the wrap boundary was still doubling lines

Cycle 4's fix took the line back by the rows it occupied. At a length that is an **exact
multiple of the width**, it was still off by one, and the line appeared twice again.

The cause is that two terminals disagree about where the cursor is. Sent exactly as many
characters as it has columns, the VT-series and xterm hold it at the last column with the
wrap *pending*; a simpler terminal has already moved to the next row. Neither is wrong, and
`_erase` cannot tell which it is talking to. Guessing one way leaves a duplicated row;
guessing the other climbs a row too far and erases a line already committed.

Measured before the fix, at width 40:

| line length | 38 | 39 | **40** | **41** | **42** | **80** | **81** |
|---|---|---|---|---|---|---|---|
| shown correctly | ok | ok | doubled | doubled | doubled | doubled | doubled |

41 and 42 double for the same reason as 40: the echo count lags the line by one chunk, so
the *echoed* length is 40 in all three cases.

**Rather than pick a side, the boundary is never reached.** One character is held back when
the echo would land exactly on a multiple of the width; it arrives with the next chunk, or
with the line. It costs a few hundred microseconds and removes the whole class.

## Finding 2 — the erase measured against the wrong window

`_rows_used` used the width in force **at the newline**, not the width the text was
**echoed** at. A window narrowed in between makes that number far too large: at 200 columns
down to 20, a 150-character line goes from nought rows to seven, and seven rows up is into
the answer already on screen.

Terminals disagree about whether they reflow what is already drawn — Windows Terminal does,
xterm does not — so **there is no arithmetic that is right for both**. Measuring what was
actually emitted is the one that fails safely: leftover text, never a destroyed answer.
That direction is now pinned by a test.

This is AC 13, which cycle 3 measured by changing the width between *lines* and cycle 4 did
not revisit. Changing it *within* a line is the case that costs something.

## Finding 3 — cycle 4's own fix, reintroduced by its own test

Cycle 4 fixed a ragged table coming back as a paragraph of pipes, by asking whether Rich
had drawn a table. It asked by looking for the header rule character being **present** in
the output. A row like `| a─b | c |` — a model drawing a diagram in a cell — therefore
counted as proof, and the paragraph Rich actually produced was handed back with every row
run together. The exact bug cycle 4 had just fixed.

A rule is now a line that is *nothing but* rule, which is what a rule is.

---

## Three stale breaks

`.tmp/break60.py` reported nothing wrong while three of its breaks no longer matched any
line in the file — cycle 4 had moved the code under them. A stale break is silent: it
prints a NOT APPLIED line among two dozen others and the run still says "no survivors".

That makes **five breaks now found to be no-ops** across this row: `[] or X` is `X`, an
anchored `re.match` that could never match mid-line, and these three. The harness needs the
same suspicion as the tests, for the same reason.

---

## What was attacked and came back clean

| Input or claim | Result |
|---|---|
| a wide character straddling the wrap point, at four offsets | clean |
| an empty line inside a fence | clean |
| a line inside a fence that lexes to nothing | clean |
| a half-arrived fence opener, one character at a time | clean — `` ```pyth `` shown literally, no language guessed (AC 9) |
| a 200-line fenced block, context bounded | clean, and the last line is not lost |
| the two plain paths — not a terminal, and the switch | **byte for byte identical**, and no escape in either. Not two branches that agree: one branch |
| can a reply be pending at `report_too_large`? | no — both call sites are before streaming, so nothing is in flight |
| can a reply be pending at `note_round_limit`, `report_truncated`, `show_sources`? | no — all three follow `end_reply` |
| a live reply through the local Ollama | clean, and `f"Hello, {name}!"` highlights the interpolation inside the string |

## AC 6 and the table — a decision, recorded

Cycle 5's action asked whether holding a table for four seconds is consistent with AC 6.

**It is, and the criterion is met.** AC 6 reads *"Formatting appears as the reply streams.
The user does not wait for the whole reply before seeing any of it."* Prose formats
immediately, and a held table's rows are **visible as they are typed** — the raw row is on
screen while it arrives, then taken back when the drawn table replaces it. What waits is the
table's *formatting*, not the reply's, and not the content.

The alternative readings were considered and rejected: showing rows as raw pipes forever
fails AC 1, and drawing the table incrementally requires redrawing rows already shown, which
fails AC 7. Nothing was left unexamined because cycle 3 had recorded a reason.

---

## Status of all 29

**Met, with evidence.** 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 20,
21, 22, 23, 24, 25, 26, 27, 28.

**Met by the transcript being unchanged, plus a rendered-session assertion for 17 and 18.**
19, 29.

---

## What cycle 6 does

**A third read**, narrowed to what cycle 5 touched: the echo limit, the remembered echo
width, and the rule test. The trend is what matters — cycle 4 found four in cycle 3's code,
cycle 5 found three in cycle 4's. Each fix is new code and new code is where defects are.

**The stopping rule is a read that finds nothing**, or the fail-safe at 07:07 IST. A cycle
that finds something writes another; a cycle that finds nothing takes exit 1 and closes the
queue. That rule is external to the reading and does not depend on the reader's judgement
about its own work, which is the point.

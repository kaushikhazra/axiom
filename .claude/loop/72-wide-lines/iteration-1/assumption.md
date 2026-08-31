# Assumptions

Standing inputs. May change between iterations — when one does, say so in that cycle's Observe.

- **The defect is `soft_wrap=True` in `_as_markdown`** (`src/axiom/terminal.py`). Measured
  at 60 columns: a paragraph of 180 characters comes back 179 visible, a heading 182 comes
  back 179, but a quote of 182 comes back **58** and a bullet and a numbered item of 182
  come back **60**. Rich renders a quote or a list item inside a container; `soft_wrap`
  becomes no-wrap plus a fixed-width box, and the container crops. A bare paragraph has no
  container, so it passes through whole and the terminal wraps it.
- **The terminal does the wrapping today, and should keep doing it where it already
  works.** Paragraphs and headings are emitted as one long line on purpose. Whatever fixes
  the container case must not start hard-wrapping the cases that are already correct — that
  is what the *Unchanged* group of #72 is guarding.
- **`_erase` / `_rows_used` are load-bearing and were earned.** They exist because a line
  that occupies three rows must be taken back by three rows or the paragraph appears twice
  — the exact defect that made #60 AC 7 fail twice while "no cursor-up is ever emitted"
  was counted as proof. A fix that changes how many rows a line occupies must be checked
  against them.
- **The source is `src/axiom/terminal.py` and the tests are `tests/`.** This iteration
  folder holds the loop's own files and logs, nothing else. Never copy source into it.
- **No new dependency.** Rich and pygments are already here; nothing else gets added for
  this.
- **`.tmp/probe.py` is the loop's measuring instrument**, not a deliverable. It may be
  extended. It is gitignored and never committed.
- **Do not touch the nesting defect.** That is issue #73 and its own loop, in the same
  function. Leave it alone even when it is obviously adjacent, or two loops will fight over
  one file and neither log will mean anything.

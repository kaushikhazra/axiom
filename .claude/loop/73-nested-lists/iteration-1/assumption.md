# Assumptions

Standing inputs. May change between iterations — when one does, say so in that cycle's Observe.

- **The cause is that `_as_markdown` renders one line in isolation.** Measured at 80
  columns: `'- Outer'` and `'  - Inner'` both come back at the same column with the same
  marker; `'1. One'` and `'   1. One point one'` both come back as ` 1 `; and
  `'    - Deepest'` comes back as a **code block** with blank padded lines around it,
  because four spaces of indent means code to a renderer that cannot see it is inside a
  list. Markdown is context-sensitive and a single line carries no context.
- **Line-at-a-time rendering is not the thing to change.** It is what makes the reply
  stream, which is the whole of #60 — AC 6, AC 8 and AC 10 all depend on it, and holding
  lines back to gain context would break them. The renderer must therefore **track list
  depth itself across lines** and place the indent, rather than asking Rich to infer it.
- **A table is the only construct allowed to be held back.** That rule is in the code's own
  comments and it is load-bearing: AC 8 forbids holding a fence's contents and AC 10 forbids
  holding anything else. Nesting must be solved without holding a second thing.
- **The source is `src/axiom/terminal.py` and the tests are `tests/`.** This iteration
  folder holds the loop's own files and logs, nothing else. Never copy source into it.
- **No new dependency.** Rich and pygments are already here.
- **`.tmp/probe_nesting.py` is the measuring instrument**, not a deliverable. Gitignored,
  never committed.
- **Do not touch the wrapping defect.** That is issue #72 and its own loop, in the same
  function. Both loops edit `_as_markdown`; leave the other one's problem alone, or neither
  log will mean anything. If #72 has already landed a change, read it before editing and
  build on it rather than reverting it.

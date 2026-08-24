# Observe

Record each cycle:

- Every one of the 19 acceptance criteria in issue #26, each marked **met** / **not met** / **untested**, with the evidence that settles it — a test name, a command and its output, or a transcript. A criterion with no evidence is **untested**, never met.
- How far that moved from the last cycle, and what moved it.
- What is still missing, and whether it can be closed from here at all.
- Any assumption that changed.

Read the criteria from the live issue each cycle — `gh issue view 26 --repo kaushikhazra/axiom` — not from memory or from a copy.

Evidence rules:

- A criterion about what the user sees is settled by running the program and pasting the transcript, not by reading the source.
- A criterion about failure is settled by causing that failure, not by inspecting the handler.
- Passing tests are evidence. Tests written but not run are not.

Goal check:

- **Met** — all 19 criteria are met with evidence. The loop ends.
- **Not met** — report and write the next action.
- **Answer did not move** — report the flat result and stop. Do not run another variant.

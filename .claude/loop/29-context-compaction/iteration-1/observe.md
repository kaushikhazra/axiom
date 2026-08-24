# Observe

Record each cycle:

- Every one of the 11 acceptance criteria in issue #29, each marked **met** / **not met** / **untested**, with the evidence that settles it — a test name, a command and its output, or a transcript. A criterion with no evidence is **untested**, never met.
- How far that moved from the last cycle, and what moved it.
- What is still missing, and whether it can be closed from here at all.
- Any assumption that changed.

Read the criteria from the live issue each cycle — `gh issue view 29 --repo kaushikhazra/axiom` — not from memory or from a copy.

Evidence rules:

- A criterion about what the user sees is settled by running the program and pasting the transcript, not by reading the source.
- A criterion about what compaction preserves (AC 6) is settled by actually asking the model a question whose answer only exists in the compacted portion, and getting it right — not by asserting the compacted text "contains" the fact.
- A criterion about size (AC 7) is settled by an actual token or character count, before and after.
- A criterion about a trigger or an escalation level is settled by actually driving the conversation to that state (real message pairs, real or forced token usage) and observing which level fires — not by unit-testing the threshold comparison in isolation, though that's fine as additional evidence.
- Passing tests are evidence. Tests written but not run are not.

Goal check:

- **Met** — all 11 criteria are met with evidence. The loop ends.
- **Not met** — report and write the next action.
- **Answer did not move** — report the flat result and stop. Do not run another variant.

# Observe

Record each cycle:

- A status token for **every one of #33's 20 criteria**, grouped under #33's own headers:
  `not-started` / `attempted` / `met-with-evidence` / `blocked`. All 20 get a token every
  cycle, even "no change." Cite them as "AC 7", matching the numbering in the issue.
- How far that moved from the last cycle, and what moved it.
- What is still missing, and whether it can be closed from here at all.
- Any assumption that changed.

Evidence rules - this is a refactor, so the failure mode is not "it doesn't work," it is
"it works differently and nobody noticed." Claims are settled by comparison against a
recorded baseline, never by inspection alone:

- **Cycle 1 writes no code.** It reads what exists and records the baseline the rest of the
  loop is measured against: (a) a captured transcript of observable behaviour - startup line,
  a normal exchange, each error path, each exit path, and the exit status of each; (b) an
  inventory of every assertion in `tests/`, by test name; (c) `wc -l` of `src/`. Without that
  baseline, AC 1, AC 2 and AC 14 cannot be settled at all.
- **AC 1 is closed by a before/after diff of the captured transcript, not by reasoning.**
  "The output should be the same" is not evidence. A recorded identical transcript is.
- **AC 2 is closed by comparing the assertion inventory**, showing each baseline assertion
  still present somewhere - renamed or relocated is fine, absent or loosened is not. A test
  count is not an assertion inventory.
- **AC 4 is closed by performing the test, not describing it**: for each of its five kinds of
  change, name the single module that would be edited, and confirm no second module appears
  in more than one of the five lists for the same reason.
- **AC 8 and AC 11 are closed by grep** - the session module naming no vendor or HTTP client,
  and no literal appearing in two places. Paste the command and its output.
- **AC 13 and AC 14 are closed by counting**, not by judgement. `wc -l` against the baseline;
  the 50% cap is 447 lines.
- **The full suite is re-run in every cycle that changes code**, and the result recorded.
  A cycle that edits code and does not record a suite result has not finished.
- **The suite must pass with no Ollama running.** If any test needs a live model, that is a
  failure of AC 20, not a caveat.
- If a cycle finds that a criterion cannot be met as written, say so plainly and say why.
  Do not quietly reinterpret a criterion to make it passable.

Goal check:

- **Met** - all 20 criteria are `met-with-evidence`, and the suite is green. The loop ends.
- **Not met** - report which criteria moved and which did not, and write the next action.
- **Answer did not move** - report the flat result and stop. Do not run another variant.

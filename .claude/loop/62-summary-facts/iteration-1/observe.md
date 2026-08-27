# Observe

Record each cycle:

- A status token for **every one of #62's 12 criteria**: `not-started` / `attempted` /
  `met-with-evidence` / `blocked`. All twelve get a token every cycle, even "no change."
  Cite them as "AC 4".
- How far that moved from the last cycle, and what moved it.
- What is still missing, and whether it can be closed from here at all.
- Any assumption that changed.

## This row is not like the four before it

**Most of these criteria are about what a model produces**, and `StubBackend.complete` returns a
fixed string. A test that asserts the summary holds the right things, against a stub that was
told what to return, proves only that the stub was told. That is the single largest trap here
and it is worth more attention than any individual criterion.

What **can** be settled hermetically:

- **`bounded()`'s drop order.** Given a list of facts and a limit, which go. Deterministic, and
  AC 3 lives here.
- **The instruction's content.** That it asks for what the criteria require. Weak on its own -
  an instruction is a request, not a guarantee - so never let this stand as the only evidence
  for AC 4 or AC 5.
- **Everything about honesty and bounds** - AC 6, AC 7, AC 8. Unchanged machinery from #32.
- **AC 9 to AC 11** - recall across a compaction, driven with a stub that returns a summary the
  test wrote.

What can **only** be settled against a real model:

- **AC 4, AC 5** - whether general knowledge actually stops entering the summary. This needs a
  live probe with the local Ollama, recorded in the log with the real transcript. Say plainly in
  the log which criteria rest on a live probe and which on a test.

## Where this will be tempting to cheat

**AC 3 invites a heuristic that cannot be kept.** "What goes is the least particular to this
conversation" reads like a request to *rank* facts. A scorer that guesses which bullet matters
is smarts pretending to be a guarantee - the thing Kaushik ruled out when he chose a system
prompt over axiom challenging a model. **Prefer a structural signal over a judgement**, and if
no honest structural signal exists, say so and meet AC 3 by making the summary contain only
particular facts in the first place.

**AC 4 - the instruction is a request.** Asserting the instruction *says* something is not
evidence that the model *does* it. Pair every instruction assertion with a live observation.

**AC 11 - "a conversation with nothing worth summarising produces no summary rather than an
invented one."** A small model asked to extract facts from small talk will invent some. This is
the criterion most likely to fail live while passing every test.

**AC 12 - unchanged.** #32's behaviour: when compaction runs, how it is announced, what it does
to the conversation. The golden transcript is the instrument.

## What counts as evidence

- **`bounded()` tested directly**, with hand-written fact lists. No model involved.
- **A live probe for AC 4, AC 5 and AC 11**, with the real output pasted into the log. The
  observed defect - "RPG stands for role-playing game" occupying a slot - is the case to
  reproduce and then show fixed.
- **The golden transcript** for AC 12.

## Standing checks

- **The full suite is re-run in every cycle that changes code**, and the result recorded. The
  baseline is **521 tests, green** at scaffold time, 2026-08-28 02:18 IST.
- **The suite must stay green with no Ollama running**, and must not be changeable by the
  environment:
  `env AXIOM_HOST=http://127.0.0.1:1 AXIOM_MODEL=nonsense:99b AXIOM_DEBUG_MAX_CONTEXT=7 uv run pytest -q`
  **A live probe is for the log, never for the suite.**
- **The golden transcript may change** if the instruction's text is recorded anywhere it
  reaches. Copy it aside in cycle 1, fix every stub before regenerating, read the diff as a
  diff, check `grep -c "^<"`.
- **Ask whether each test could pass if the feature did nothing**, then break the feature and
  watch it go red. **Name the survivors**, one verdict each.
- If a criterion cannot be met as written, say so plainly and say why. Given how much of this
  row depends on a model's behaviour, that is a likelier outcome here than in the last four
  rows, and it is an acceptable one.

## The cycle that writes the code never declares it done

A separate cycle checks, reading the criteria from GitHub **before** the diff and before the
previous log. **Attack each criterion rather than confirming it.**

This has found something real in **ten consecutive issues**. The recurring shapes, all live here:

- **An assertion a wrong implementation also satisfies.** #61's AC 9 had *no* test - every run
  used default settings, so a figure built from bare defaults matched by coincidence, and
  breaking it left all 520 green.
- **A default that happens to be right.** #56's `web=False`.
- **Two criteria that disagree**, found by reading them literally. #55's AC 1 against AC 7.
- **A test asserting more than its criterion**, which breaks when something correct lands. #61
  found two.

## Goal check

- **Met** - all 12 criteria `met-with-evidence`, suite green and hermetic, transcript accounted
  for, and the live probe recorded showing general knowledge no longer taking a slot.
- **Not met** - report which criteria moved and which did not, and write the next action.
- **Answer did not move** - report the flat result and stop. Do not run another variant.

# Observe

Record each cycle:

- A status token for **every one of #56's 12 criteria**: `not-started` / `attempted` /
  `met-with-evidence` / `blocked`. All twelve get a token every cycle, even "no change."
  Cite them as "AC 4".
- How far that moved from the last cycle, and what moved it.
- What is still missing, and whether it can be closed from here at all.
- Any assumption that changed.

## Where this will be tempting to cheat

**AC 5 to AC 8 - "reads the same after a switch as at startup".** The criterion is that the two
lines **agree**, and the only honest way to test agreement is to compare them against each
other. A test that hard-codes the expected wording in both places passes while they drift,
because it drifts with them. **Assert one line against the other**, generated in the same run,
and the criterion cannot rot.

**AC 1, AC 2 - the two missing facts.** Easy to add the words and never check they are right.
The web state must follow `--no-web`, and the override note must follow whether the override is
actually in force - not be printed unconditionally because a test only ever ran one way.

**AC 9 - a forced context is never presented as the model's own.** This is the *purpose* behind
AC 2. Test it as its own thing: with an override in force, the switch line must be
distinguishable from what the same model would print without one.

**AC 4 - any fact the startup line reports that a switch does not make stale.** Deliberately
open-ended, and the trap is reading it as "the two facts already named". Enumerate what
`announce()` actually reports today - model, host, context, override, tool count, web state -
and account for **every one**, saying for each whether it belongs on the switch line or is
excluded by AC 11.

**AC 10 - the web state unknowable from the line alone.** A count is not a web state. The test
must show two runs with the same tool count and different web settings, or the criterion is
being read as "print something".

**AC 12 - nothing else about a switch changes.** #49's 34 criteria still hold. The switch still
carries the conversation, still remembers, still leaves servers alone.

## What counts as evidence

- **The two lines, compared in one run.** Startup, then a switch, both captured, both parsed for
  the same facts. That is the only test that cannot drift.
- **Two settings per fact.** Web on and web off. Override in force and not. A single setting
  proves the word can be printed, not that it follows anything.
- **`StubBackend`'s `infos` and `capable`** give per-model windows and tool support, which is
  what makes a switch actually change something.

## Standing checks

- **The full suite is re-run in every cycle that changes code**, and the result recorded. The
  baseline is **490 tests, green** at scaffold time, 2026-08-28 01:11 IST.
- **The suite must stay green with no Ollama running**, and must not be changeable by the
  environment:
  `env AXIOM_HOST=http://127.0.0.1:1 AXIOM_MODEL=nonsense:99b AXIOM_DEBUG_MAX_CONTEXT=7 uv run pytest -q`
- **The golden transcript will change** if any scenario switches models. Copy it aside in cycle
  1. **Fix every stub before regenerating.** Then read the diff as a diff and check
  `grep -c "^<"` for removed lines.
- **Ask whether each test could pass if the feature did nothing**, then break the feature and
  watch it go red. Record the counts and **name the survivors**, one verdict each.
- If a criterion cannot be met as written, say so plainly and say why.

## The cycle that writes the code never declares it done

A separate cycle checks, reading the criteria from GitHub **before** the diff and before the
previous log. **Attack each criterion rather than confirming it.**

This has found something real in **eight consecutive issues** - #40 AC 7, #41 AC 9, #42 AC 3,
#43 AC 6, #48 AC 33, #49 AC 25 and AC 27, #57 AC 7, #55 AC 1 against AC 7.

Two shapes recur, and both are live here:

- **An assertion a wrong implementation also satisfies** - a substring, a count, a message right
  for the wrong reason. #57's `"could not be read"` was produced by the broken decoder too.
- **Two criteria that disagree**, discovered only by reading them literally against a state
  nobody had in mind. #55 AC 1 against AC 7 over an empty file.

## Goal check

- **Met** - all 12 criteria `met-with-evidence`, suite green and hermetic, transcript change
  accounted for line by line.
- **Not met** - report which criteria moved and which did not, and write the next action.
- **Answer did not move** - report the flat result and stop. Do not run another variant.

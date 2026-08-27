# Observe

Record each cycle:

- A status token for **every one of #61's 12 criteria**: `not-started` / `attempted` /
  `met-with-evidence` / `blocked`. All twelve get a token every cycle, even "no change."
  Cite them as "AC 4".
- How far that moved from the last cycle, and what moved it.
- What is still missing, and whether it can be closed from here at all.
- Any assumption that changed.

## Where this will be tempting to cheat

**AC 9 - the figure comes from the same measurement the size checks use.** The whole value of
the number is that it is the *same* number compaction reasons about. Computing it a second way -
even a more accurate way - makes the line disagree with the behaviour it is describing, which is
worse than not printing it. Assert it against `compaction.estimated_tokens` over the same
payload, not against a constant.

**AC 3 - everything that rides in every request.** Built-ins, server tools, **and the standing
prompt**. The prompt is the easy one to forget: it is held outside `messages` in `_chat`, so it
does not look like part of the conversation, and it is 154 tokens. A figure that omits it is
wrong by a fifth on this machine.

**AC 8 - the figure changes when the declared set changes.** Three settings at least: web on,
web off, and a server attached. A test with one setting proves a number can be printed.

**AC 5, AC 6 - nothing to say.** Tools off, and a model that cannot call them. Both must be
silent, and both pass trivially for an implementation that never prints anything - so pair them
with a positive, the way #55's negatives are paired.

**AC 10 - after a switch, the cost belongs to the new model's tools.** This is the criterion
#56's cold read handed over. Switching to a model that cannot call tools drops the real cost to
nothing while a startup figure would stand. Test with two models of different tool support.

**AC 11 - a run with a server attached says what it says today.** The per-server counts, the
bounds line. This row moves a line out of `note_servers`; it must not take the others with it.

## What counts as evidence

- **The figure asserted against `compaction.estimated_tokens`**, computed in the test from the
  same declarations. Never a hard-coded 653 or 807 - those are this machine, today.
- **Two settings per claim**, at least. One printed number proves nothing about what it follows.
- **The transcript** is the instrument for AC 12 and for AC 11's "as it is today".

## Standing checks

- **The full suite is re-run in every cycle that changes code**, and the result recorded. The
  baseline is **505 tests, green** at scaffold time, 2026-08-28 01:43 IST.
- **The suite must stay green with no Ollama running**, and must not be changeable by the
  environment:
  `env AXIOM_HOST=http://127.0.0.1:1 AXIOM_MODEL=nonsense:99b AXIOM_DEBUG_MAX_CONTEXT=7 uv run pytest -q`
- **The golden transcript will change** - a line appears in every scenario that has tools. Copy
  it aside in cycle 1. **Fix every stub before regenerating.** Then read the diff as a diff and
  check `grep -c "^<"`.
- **Ask whether each test could pass if the feature did nothing**, then break the feature and
  watch it go red. **Name the survivors**, one verdict each - #56's cold read found three
  passing on a coincidence only because they were named.
- If a criterion cannot be met as written, say so plainly and say why.

## The cycle that writes the code never declares it done

A separate cycle checks, reading the criteria from GitHub **before** the diff and before the
previous log. **Attack each criterion rather than confirming it.**

This has found something real in **nine consecutive issues** - #40, #41, #42, #43, #48, #49,
#57, #55, #56.

Three shapes recur, and all are live here:

- **An assertion a wrong implementation also satisfies.** #57's `"could not be read"`.
- **Two criteria that disagree**, found only by reading them literally. #55's AC 1 against AC 7.
- **A default that happens to be right**, so a broken caller looks correct. #56's
  `web=False`. **This row prints a number, and zero is a plausible number** - be careful what a
  missing figure would look like.

## Goal check

- **Met** - all 12 criteria `met-with-evidence`, suite green and hermetic, transcript change
  accounted for line by line.
- **Not met** - report which criteria moved and which did not, and write the next action.
- **Answer did not move** - report the flat result and stop. Do not run another variant.

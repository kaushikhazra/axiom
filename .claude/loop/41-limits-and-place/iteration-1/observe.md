# Observe

Record each cycle:

- A status token for **every one of #41's 12 criteria**: `not-started` / `attempted` /
  `met-with-evidence` / `blocked`. All twelve get a token every cycle, even "no change."
  Cite them as "AC 4".
- How far that moved from the last cycle, and what moved it.
- What is still missing, and whether it can be closed from here at all.
- Any assumption that changed.

## What counts as evidence

This issue is about what a model is **told**, which makes it unusually easy to fake. A test
asserting that a system prompt contains the string "30 seconds" proves axiom assembled a
sentence. It proves nothing about whether the model read it, believed it, or acted on it.

- **AC 1, 3, 4 and 5 need a real model.** They are claims about behaviour: that a model
  knows its limits, refuses to change them, stays where it was put, and still honours a path
  the user names. Evidence is a live run where the model does or does not do the thing.
- **A unit test on the assembled prompt is supporting evidence and closes nothing on its
  own** for those four. Write both.
- **AC 2, 6, 7, 8, 9, 10, 11 and 12 may be settled with stubs.** They are about what the
  code does, not what a model concludes.
- **#35 AC 12 is the warning.** It could not be met by asking a 7B model to be candid about
  what it did not know, and was replaced by axiom reporting what it had actually retrieved.
  If a criterion here turns out to depend on a small model's compliance, the same answer
  applies: make axiom do the thing rather than ask the model to.

## Where this will be tempting to cheat

**AC 3 - "told as facts, not as settings".** The easy version is wording: phrase the prompt
as a statement rather than an option. That is not the criterion. The criterion is that a
model *asking* to change one is still refused, which is already true structurally -
`tools.run()` rejects any argument a tool did not declare, and `Limits` is not in any
schema. Evidence is a live model asking, and being refused. Do not weaken this into a
prompt-wording assertion.

**AC 9 - "not run a third time".** The same command failing the same way twice. Both halves
are load-bearing: same command *and* same failure. A command that fails differently the
second time is not this case, and a different command that happens to fail the same way is
not either. Say what "the same failure" is compared on, and be precise about it.

**AC 10 - "says so, rather than ending with an empty answer".** Today the round loop falls
out of `range(MAX_TOOL_ROUNDS)` and whatever `reply` holds is what the user gets, which may
be nothing. The criterion is about the user being told the turn ended that way. It is not
satisfied by raising the round limit.

**AC 12 - "no extra output".** A run that never reaches a limit must look exactly as it does
today. The golden transcript is the instrument. A system prompt is not output, but anything
that leaks it to the screen is.

## The one that will look done before it is

**AC 8** may already be met. The existing cut message is
`[cut here - N more characters not included]`, which does distinguish "there is more" from
"that is all". Check it against the criterion honestly rather than assuming a change is
owed - and if it is already met, say so and move on. Inventing work to justify a criterion
is as wrong as skipping one.

## Standing checks

- **The full suite is re-run in every cycle that changes code**, and the result recorded.
  The baseline is **229 tests, green** at scaffold time.
- **The suite must stay green with no Ollama and no network**, and must not be changeable
  by the environment:
  `env AXIOM_HOST=http://127.0.0.1:1 AXIOM_MODEL=nonsense:99b AXIOM_DEBUG_MAX_CONTEXT=7 uv run pytest -q`
- **The golden transcript is the behaviour record**, and AC 12 is measured by it. Copy it
  aside in cycle 1. If a scenario moves, regenerate **deliberately** with
  `AXIOM_WRITE_BASELINE=1` and say exactly which lines changed and why.
- **A system prompt changes the context budget.** It rides in every request, like a tool
  declaration. #32 and #42 exist because that budget is tight. Record what it costs.
- **The tool-testing safety rules in `CLAUDE.md` bind this loop.** Live models get
  non-destructive requests only; destructive criteria are settled with a stub inside
  `tmp_path`; live-model tool tests run in `C:/Projects/.tmp/axiom-tool-sandbox`. AC 4 and
  AC 5 are about *where* work lands, so they will want to write files - inside the sandbox,
  never the repo.
- If a criterion cannot be met as written, say so plainly and say why. #35 ended with one
  criterion replaced on evidence and #32 with three amended. That is an acceptable outcome;
  quietly reinterpreting one is not.

## The cycle that writes the code never declares it done

A separate cycle checks, and it reads the criteria from GitHub **before** the diff and
before the previous cycle's log - that log is persuasive because its author wrote both the
code and the verdict.

**Attack each criterion rather than confirming it.** #40's cycle 2 proved AC 7 with a test
that could not have failed, and cycle 3 broke it with one hostile input. That is the
standard here.

## Goal check

- **Met** - all 12 criteria `met-with-evidence`, the four behavioural ones from a live model,
  the suite green and hermetic, the transcript accounted for. The loop ends.
- **Not met** - report which criteria moved and which did not, and write the next action.
- **Answer did not move** - report the flat result and stop. Do not run another variant.

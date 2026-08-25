# Observe

Record each cycle:

- A status token for **every one of #40's 12 criteria**: `not-started` / `attempted` /
  `met-with-evidence` / `blocked`. All twelve get a token every cycle, even "no change."
  Cite them as "AC 4".
- How far that moved from the last cycle, and what moved it.
- What is still missing, and whether it can be closed from here at all.
- Any assumption that changed.

## What counts as evidence

This issue exists because a library was believed to do something it does not do.
`trafilatura.extract` was reached for as "get the text out of a page" and it is narrower
than that. **Do not replace one belief about a library with another belief about a
library.**

- **Probe the real behaviour before designing against it.** What `trafilatura.extract`
  returns for `text/plain`, for markdown, for csv, for javascript, and for an empty body,
  are five facts to be measured in one short script, not reasoned about. Both hypotheses
  reasoned from the code alone in #34 and #35 were wrong; every probed one held.
- **AC 1, 2, 3, 6 and 7 need responses that were really served.** A hand-built
  `httpx.Response` proves the branch was taken; it does not prove that a real server
  serving a real raw file produces the headers the branch keys on. Fetch a real raw source
  file, a real README, a real robots.txt, a real PDF, and record the exact `Content-Type`
  each returned.
- **A unit test with a stubbed response is good supporting evidence and closes nothing on
  its own** for those five. Write both.
- **AC 4, 5, 8, 9, 10, 11 and 12 may be settled with stubs.** They are about what the code
  does with a response it is handed.

## Three states, not two - the decided shape

`fetch_page` has two outcomes today: content, or an `error:` string. #40 needs three, and
`assumption.md` records all three as settled by Kaushik. They are not open questions.

| the page | the model gets | the sources line |
|---|---|---|
| readable text or HTML | its content, cut to the bound if long | named |
| empty | a warning that it is empty - not an error | **not** named |
| not text at all | told it could not be read, and **none of the content** | **not** named |

The middle row is the one with no mechanism today. `__init__.py` decides a source by
`not result.startswith("error:")`, so a warning that is not an error currently becomes a
source. **That is the seam this issue has to open**, and it is the first thing to design in
cycle 2. Whatever carries the third state, `terminal.py` still owns every print.

A typeless page joins the first row: no `Content-Type` means text, because text is the only
treatment that can hand back exactly what was served.

## A cycle never stops to ask

This loop runs unattended and the queue runs loops back to back. A cycle that ends with a
question does not pause for an answer - it burns every remaining cycle until the fail-safe
and strands the loops behind it.

So: **decide, record, continue.** Where something is genuinely ambiguous, take the
reversible and least surprising option, write it into the cycle log under a heading that
says a decision was made and why, and carry it into the handover. Never write a question
into the next `action.md`.

The exception is safety, not uncertainty - if proceeding would destroy something, leak
something, or merge behaviour nobody has verified, that is `loop.md` exit 3. Being unsure
is not that.

## The failure this must not introduce

AC 6 is the dangerous criterion. A PDF, an image or an archive must be reported as not
readable, **and its bytes never returned as though they were content**. Note that
`page.text` will happily decode binary into mojibake and hand back a plausible-looking
string. So:

- The content type is judged **before** anything touches `page.text`.
- The test asserts on what the model was given, not on the message axiom printed. A tool
  that says "not readable" while returning 40KB of decoded binary has passed a message test
  and failed the criterion.

## Standing checks

- **The full suite is re-run in every cycle that changes code**, and the result recorded.
  The baseline is **193 tests, green** at scaffold time.
- **The suite must stay green with no Ollama and no network**, and must not be changeable
  by the environment:
  `env AXIOM_HOST=http://127.0.0.1:1 AXIOM_MODEL=nonsense:99b AXIOM_DEBUG_MAX_CONTEXT=7 uv run pytest -q`
- **The golden transcript is the behaviour record.** #40 changes what a user is told about
  some pages, so if a scenario there moves, regenerate it **deliberately** with
  `AXIOM_WRITE_BASELINE=1` and say in the log exactly which lines changed and why.
  Regenerating it to clear a failure is the one move that destroys its value.
- **#33's structure, #34's seam and #35's tools are kept.** `httpx` and `trafilatura` stay
  inside `tools.py`; only `terminal.py` prints; tests inject rather than patch.
- **AC 12 is a whole group on its own.** Unreachable address, error status, fetch past the
  time limit, cancelled fetch - four behaviours, each checked explicitly, not assumed
  intact because the suite is green.
- If a criterion cannot be met as written, say so plainly and say why. #35 ended with one
  criterion replaced on evidence and #32 with three amended; that is an acceptable outcome,
  and quietly reinterpreting one is not.

## The convergence check is external

A loop cannot be its own convergence detector. Before declaring the goal met, the criteria
are checked by a reading that does not have this loop's context - the criteria and the
artifact, without the reasoning that produced it. A cycle that convinces itself is the
failure mode this rule exists for.

## Goal check

- **Met** - all 12 criteria are `met-with-evidence`, the content-type ones against really
  served responses, the suite green and hermetic, and the transcript cleared. The loop ends.
- **Not met** - report which criteria moved and which did not, and write the next action.
- **Answer did not move** - report the flat result and stop. Do not run another variant.

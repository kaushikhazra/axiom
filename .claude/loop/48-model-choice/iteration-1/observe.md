# Observe

Record each cycle:

- A status token for **every one of #48's 38 criteria**: `not-started` / `attempted` /
  `met-with-evidence` / `blocked`. All thirty-eight get a token every cycle, even "no change."
  Cite them as "AC 14".
- How far that moved from the last cycle, and what moved it.
- What is still missing, and whether it can be closed from here at all.
- Any assumption that changed.

## Where this will be tempting to cheat

**AC 6 - the order is stable.** This is the one most likely to be marked met by a test that
could not fail. A stub returning a fixed list is *already* in a fixed order, so asserting the
display matches it proves nothing about sorting. The measured fact is that Ollama's
`/api/tags` returns **newest-modified first** - on this machine `gemma2:2b`, `qwen2.5-coder:7b`,
`gemma4:e2b`, `ornith:9b`, `qwen2.5:7b` - so a single `ollama pull` renumbers the list. The
test must hand the stub the host's order and assert the *displayed* order differs from it and
stays put across two different host orders.

**AC 14 - only a user's own pick is remembered.** The positive is easy. The criterion is four
negatives: a flag, an environment variable, the single-model case, and the non-terminal case,
each of which must leave the stored choice **unchanged**. An assertion that the file did not
change passes trivially if the code never writes the file at all, so every negative must sit
beside a positive proving the write path works.

**AC 2 - axiom carries no built-in model name.** Not provable by a passing test; provable by
the absence of `DEFAULT_MODEL` from `config.py` and by nothing under `src/` naming a model.
Grep for it and record the grep, rather than asserting a behaviour that would also hold if a
default were merely unused on the happy path.

**AC 31, 32 - exits with a non-zero status.** `main()` returns `None` today and **nothing in
axiom has ever exited non-zero**. A test asserting the error message was printed says nothing
about the status code. Measure the process's actual exit status.

**AC 18 - a piped first message is never consumed as an answer.** Prove it by piping a real
message and asserting it reached the model, not by asserting no prompt was printed.

**AC 30 - the folder is announced the first time.** Two runs: the first says it, the second
does not. A single-run test cannot see the difference.

**AC 12, 13 - remembered per host, and per directory.** Both are about two things not
crossing. One host and one directory can never show it.

## What counts as evidence

- **Every criterion is settled against a stub, not against Ollama.** The suite must pass with
  nothing running - see Standing checks.
- **A live probe against the local Ollama is for the implementer, not for the suite.** Use it
  to check the picker feels right and the list reads correctly; never let a test depend on it.
- **AC 22, 28 - "named on screen"** are transcript-level facts. The golden transcript is the
  instrument.
- **AC 34 - the choice cannot be saved.** A read-only directory behaves differently on
  Windows than the obvious `chmod` assumption. If it cannot be produced honestly, make the
  save path fail the way it would really fail and say in the log which mechanism was used.

## Standing checks

- **The full suite is re-run in every cycle that changes code**, and the result recorded. The
  baseline is **317 tests, green** at scaffold time, 2026-08-27 11:41 IST.
- **The suite must stay green with no Ollama running**, and must not be changeable by the
  environment:
  `env AXIOM_HOST=http://127.0.0.1:1 AXIOM_MODEL=nonsense:99b AXIOM_DEBUG_MAX_CONTEXT=7 uv run pytest -q`
  This matters more here than in any previous row: **this issue is entirely about asking
  Ollama a question**, and the lazy fix is a test that quietly needs a live host.
- **The golden transcript will change, deliberately.** The startup line's model now has a
  different provenance. Copy the transcript aside in cycle 1, regenerate on purpose with
  `AXIOM_WRITE_BASELINE=1`, and record exactly which lines changed and why.
- **Before regenerating the transcript, run `diff` and read all of it**, checking for removed
  lines explicitly. #41 cycle 2 regenerated off pytest's assertion summary - which names only
  the first differing index - and destroyed two compaction scenarios.
- **A stub that contradicts the thing under test proves nothing.** #40 found `given_page`
  announcing `text/plain` over HTML; #41 found `StubClient` reporting `prompt_eval_count=1`
  whatever it was sent. A stub model list that is already sorted is this row's version.
- **Ask whether each test could pass if the feature did nothing**, then break the feature and
  watch it go red. #43's lifetime tests held for any implementation at all.
- If a criterion cannot be met as written, say so plainly and say why. #35 replaced one, #32
  amended three, and #40, #41, #42 and #43 each had one broken by the cold read. That is an
  acceptable outcome; quietly reinterpreting one is not.

## The cycle that writes the code never declares it done

A separate cycle checks, reading the criteria from GitHub **before** the diff and before the
previous log. **Attack each criterion rather than confirming it.**

This has now found a real defect in **four consecutive issues**, every time after the
implementing cycle had written `met-with-evidence` beside it:

- #40 AC 7 - a typeless PNG returned its bytes as content and was counted as a source.
- #41 AC 9 - the retry block compared whole result strings, so a pid in the output defeated it.
- #42 AC 3 - the fix compacted away the user's own message, so the model answered a question
  it had never seen.
- #43 AC 6 - a server whose name contained the separator declared tools that could never be
  called.

Each was found by a hostile input. None by rereading code.

## Goal check

- **Met** - all 38 criteria `met-with-evidence`, the suite green and hermetic with no Ollama,
  the transcript's change accounted for line by line.
- **Not met** - report which criteria moved and which did not, and write the next action.
- **Answer did not move** - report the flat result and stop. Do not run another variant.

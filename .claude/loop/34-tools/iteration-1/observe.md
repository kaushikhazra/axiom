# Observe

Record each cycle:

- A status token for **every one of #34's 35 criteria**, grouped under the issue's own
  headers: `not-started` / `attempted` / `met-with-evidence` / `blocked`. All 35 get a token
  every cycle, even "no change." Cite them as "AC 12", matching the issue's numbering.
- How far that moved from the last cycle, and what moved it.
- What is still missing, and whether it can be closed from here at all.
- Any assumption that changed.

## What counts as evidence

**A stub is enough for most of this. It is not enough for the model-facing criteria.**
The whole risk in #34 is that tool calling works on one model and silently fails on the
next, and a stub cannot tell you that - a stub does whatever we wrote it to do.

- **AC 3, 6, 7 and 8 require live runs against real models.** Name the model and paste what
  it actually did. AC 3 needs three families in one cycle: `qwen2.5:7b` (qwen2),
  `gemma4:e2b` (gemma4), `ornith:9b` (qwen35). AC 8 needs the tool-less model.
- **Everything else may be settled with stubs**, and should be - live runs are slow and
  swapping 5-7GB models on a 16GB machine is slower still. Do not burn a cycle proving with
  a live model what a stub proves faster.
- **A live run that fails is evidence, not a wasted cycle.** Record what the model emitted
  verbatim. A model announcing its call as text rather than structured output is exactly
  what AC 6 is about, and the raw output is the only way to design for it.

## Safety - binding, not advisory

`CLAUDE.md`'s "Testing tools before security exists" section governs every cycle. The
security stories have not landed, so nothing inspects what a tool is asked to do.

- **A live model is only ever asked for non-destructive work.** Read, list, echo,
  `python -c "print(...)"`, create a file in the sandbox. Never a request that deletes,
  moves or overwrites; never `git`; never the network.
- **Destructive criteria are settled with a stub.** AC 12 - deleting a file - is a
  deterministic tool call the test wrote itself, inside pytest's `tmp_path`. A live model is
  never asked to improvise its way to a delete.
- **Live-model tool tests run in `C:/Projects/.tmp/axiom-tool-sandbox`**, never the repo and
  never a drive root.

A cycle that breaks one of these has failed, whatever else it achieved. Say so in the log.

## The golden transcript

`tests/baseline/transcript.txt` is the behaviour record from #33. **This loop will change it
legitimately** - AC 1 puts tool availability in the startup line, so the recorded startup
line must change.

When it does: regenerate with `AXIOM_WRITE_BASELINE=1`, and in that cycle's log state
**exactly which lines changed and why each change was intended**. A regeneration with no such
statement is indistinguishable from covering up a regression, which is the whole thing the
transcript exists to prevent.

Add the new observable paths to the harness as they appear - a tool running, a tool failing,
a tool cancelled. #34 adds behaviour the thirteen existing scenarios do not reach.

## Standing checks

- **The full suite is re-run in every cycle that changes code**, and the result recorded.
- **The suite must stay green with no Ollama running and must not be changeable by the
  environment**, provable in one command:
  `env AXIOM_HOST=http://127.0.0.1:1 AXIOM_MODEL=nonsense:99b AXIOM_DEBUG_MAX_CONTEXT=7 uv run pytest -q`
- **#33's structure is kept.** Tools do not get to reintroduce a god-module: no module both
  talks to a backend and writes to the terminal, and `ollama` and `httpx` stay inside
  `backend.py`. Check by grep when a cycle adds a module.
- If a criterion cannot be met as written, say so plainly and say why. Do not quietly
  reinterpret one to make it passable.

## Goal check

- **Met** - all 35 criteria are `met-with-evidence`, the model-facing ones by live runs, and
  the suite is green. The loop ends.
- **Not met** - report which criteria moved and which did not, and write the next action.
- **Answer did not move** - report the flat result and stop. Do not run another variant.

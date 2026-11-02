# Observe

## What to record, every cycle

- **The count.** How many of #95's criteria are met, out of how many (`gh issue view 95`
  gives both). A row counts as met only when a test or a driven transcript backs it, named
  in the log. Write the number. It is the thing that has to move.
- What moved it. One sentence.
- What is still missing, and whether it can be closed from here at all.
- The suite: passed, deselected, wall clock. All three, every cycle.
- Any assumption that changed.

## Goal check

- **Met** — every criterion backed, suite green, and the live run shown. The loop ends.
- **Not met** — report and write the next action.
- **The count did not move for two consecutive cycles** — report the flat result and stop.

## The criteria that will be got wrong

| | why it will be got wrong |
|---|---|
| **AC 10** — told in one session, answered in the next | A stub that returns the fact proves nothing. Needs a real Ollama model and the real Synaptra, and the memory seen in the store. **Owed until the orchestrator gives the GPU go.** |
| **AC 16** — nothing relevant adds nothing | Synaptra's recall returns a ranked list with no similarity score, so "relevant" is a judgement axiom has to make from `found_by`. A test with a hand-made result proves the filter, not that the filter is right. Calibrate live. |
| **AC 13** — a failed store is not reported as remembered | The model, not axiom, writes the reply. Axiom controls the tool result and the line the user sees. Say which half a test covers. |
| **AC 9** — quit during the download | Needs a process killed mid-install. Use a script this repo owns as the installer, never the network. |
| **AC 5, AC 6** — axiom's own packages untouched | A negative. Establish it by comparing the installed `mcp` version before and after, in a real setup. |
| **AC 20, AC 22** — no leftover process | #43 AC 26 and AC 27 prove the assumption "the library closes it" wrong once already. Check the process list. |

## What proves a row

- Behaviour: a test, named in the log.
- What reaches a screen: a transcript or a rendered sample in `logs/`.
- A negative: the sweep that establishes it, and what was swept.
- Needs a live model or the network: named as owed and left owed. **A cycle never claims a
  row it could not drive.**

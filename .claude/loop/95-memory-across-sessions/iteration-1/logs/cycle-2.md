# Cycle 2 — 2026-11-02

Read #95 first (`gh issue view 95`): 22 criteria, AC 7 amended by the owner's ruling this
afternoon (uv's package cache and any Python it fetches may stay outside the project; no
`--no-cache`). Hold on heavy work lifted by the orchestrator at 08:22 UTC.

## The count

**22 of 22 backed.** Moved from 15: AC 4, 7, 8, 10, 11, 14, 20, 21.

| AC | now | backed by |
|---|---|---|
| 4 server over the start limit says memory is unavailable | met | `test_a_memory_server_that_will_not_start_is_called_memory`, `..._not_memorys_is_left_alone` |
| 7 (amended) server, venv and memories inside the project | met | live A: `.axiom/memory/` held `venv/`, `data/`, `ready`; axiom's `mcp` 2.1.1 before and after. Not swept for other writes: the criterion now allows uv's cache, a fetched Python, the model cache |
| 8 README states what the first run adds | met | README: "What you need", "Memory", the `--no-memory` row, the `.axiom/memory/` row |
| 10 told in one session, answered in the next, real model, memory seen in the store | met | below |
| 11 each memory carries the model's name | met, **and corrected** | below |
| 14 axiom never stores by itself | met | `test_axiom_never_stores_a_conversation_by_itself` |
| 20 two projects do not share memories | met | `test_two_projects_keep_separate_memories` (a data directory each, inside it) |
| 21 a server that dies mid-session | met | `test_a_memory_server_that_dies_mid_session_is_said_and_the_chat_goes_on` kills the real process |

### AC 10, the live pair (gemma4:e2b, the real Synaptra, `C:/Projects/.tmp/axiom-synaptra-live/project`)

Store emptied first, so nothing from cycle 1's session could answer.

    session 1  typed: please remember this for later: my dog is called Rex and I work in Kolkata.
               axiom: synaptra__memory_store(content=my dog is called Rex and I work in Kolkata)
                 | stored: my dog is called Rex and I work in Kolkata
               I have remembered that your dog is called Rex and you work in Kolkata for later.
    session 2  (new process)  typed: what is my dog called, and which city do I work in?
               axiom: memory: 1 from earlier sessions
               Your dog is called Rex, and you work in Kolkata.

The store, listed straight from the server afterwards (`memory_list`, not recall):
`my dog is called Rex and I work in Kolkata`, type `episodic`, in
`.axiom/memory/data`. The session-2 answer came after a 0.4 s recall, with no tool call by
the model.

### AC 11, corrected

Cycle 1 marked AC 11 met on a test that checked the `rater` argument. **That was the wrong
evidence.** Listed from the real server, the memory showed `rater: auto:heuristic` and
`source: None`: Synaptra keeps the rater only when an importance is passed with it, and
axiom passes none, so the model's name appeared nowhere in the memory. Fix: `source` is
also set, to `axiom:<model>`, a field the server keeps as given. Confirmed on the real
server: `source: 'axiom:gemma4:e2b'`. The fake server and the test were changed to match.

## Suite

1086 passed, 9 failed, 1 skipped, 1 deselected, 183 s, then 2 more passed after the kill
test was added (44 in `tests/test_memory.py`). **The 9 failures are the baseline's**
(1043 passed, 9 failed before any change): the colour and rendering assertions in
`test_characterization`, `test_facts` x2, `test_indented_code`, `test_multiline`,
`test_rendering` x4. Run with `PYTHONPATH=src`; the checkout's venv was built for
`C:\Projects\axiom` and does not import `axiom`.

## Accepted rather than fixed

- **Recall is by shared word.** A paraphrase misses ("tell me about my pet" does not find a
  memory about a dog). Synaptra's recall returns no similarity, and its score is the same
  for a relevant and an irrelevant memory. The owner's ruling: ship it, limit written down
  (README, `memory.py`); a similarity score is a separate issue for the Synaptra maintainer.
- **A generic word can recall a memory it should not** ("called", "live" matched the cat
  memory for a question about the dog's name). The stoplist is short on purpose.
- **What the model writes after a refused store is its own.** Axiom controls the tool
  result and the line the user sees (both say NOT stored), not the reply.
- **The startup line says "server start limit 30s"** while memory's own limit is 120 s.
- **The first run is Windows-measured** (875 MB, 175 MB, 136 s). Linux's default torch build
  is far larger; the figures in the first-run text are approximate and say so.

## Release blocker (recorded on #95, 2026-11-02)

Synaptra must move to mcp 2.x before any axiom release. Until then it lives in its own venv
because synaptra 2.1.1 requires `mcp<2.0` and axiom needs `mcp>=2.1.1`.

## Why the loop stops

Converged on the criteria: 22 of 22 backed. **This is not the loop declaring itself done.**
The external check is the owner's: the first run downloads about a gigabyte and the answer
depends on a model, so it needs Kaushik to try it by hand in a fresh folder, ask a fact in
a second session, and say whether the experience is acceptable. Nothing merges to `master`
from here; the orchestrator opens the pull request.

# Cycle 1 — 2026-11-02

Read #95 first (`gh issue view 95`): 22 criteria. Branch `feature/95-memory-across-sessions`
off `master` 40a9448.

## The count

**15 of 22 backed. 7 owed.**

| AC | state | backed by |
|---|---|---|
| 1 first run says what, how large, where; shows progress | met | `test_the_first_run_says_what_it_fetches_before_it_fetches_it`; live A printed the plan, then uv's and the model's own progress |
| 2 later runs download nothing | met | `test_a_later_run_downloads_and_says_nothing`; live B sessions started with no download |
| 3 setup cannot finish: plain chat, one-line reason, retried | met | `test_a_setup_that_failed_leaves_a_plain_chat_and_a_one_line_reason`, `..._is_tried_again` |
| 4 server over the start limit: starts anyway, says unavailable | **owed** | the generic failure path exists (#43) and reads `synaptra: <reason>`; not the words "memory unavailable", not driven |
| 5 user runs nothing but axiom | met | `ensure` is called from `_chat`; no setup command exists; `test_memory_follows_tools_and_mcp_and_its_own_switch` |
| 6 own venv; axiom's `mcp` unchanged | met | live A: axiom `mcp` 2.1.1 before and after, project venv has 1.30.0 |
| 7 nothing written outside the folder but the model | **owed, probably not met** | see finding 3 |
| 8 README states what first run adds | **owed** | not written |
| 9 quit mid-download leaves nothing that blocks the next run | met | `ready` written last, stale venv removed, child killed: four tests. A real kill was not driven |
| 10 fact told, quit, new session answers, real model | **owed** | store worked live; recall did not on the first attempt; fixed since, not re-driven |
| 11 each memory carries the model's name | met | `test_a_store_gets_the_name_of_the_model_that_made_it`; live recheck owed |
| 12 one line saying what was stored | met | live: `\| stored: My cat is called Biscuit and I live in Pune.` |
| 13 failed store is not reported as remembered | met | tool result and the user's line both say NOT stored; what the model then writes is its own |
| 14 axiom never stores by itself | **owed** | true by construction, no test names it |
| 15 relevant memories reach the model without a tool call | met | tests on a stand-in; `recall_for` against the real store, CPU only |
| 16 nothing relevant adds nothing | met, with a limit | real store: weather, haiku, "my pet" returned nothing; "my pet" is a paraphrase it misses |
| 17 only store and recall offered | met | live: `synaptra: 2 tools` |
| 18 empty store, normal reply | met | `test_an_empty_store_changes_nothing_the_model_sees` |
| 19 memories survive quitting | met | session 1 stored; later fresh processes read it |
| 20 two projects do not see each other | **owed** | per-project data dir by construction, no test |
| 21 server stops mid-session | **owed** | recall failure is handled and shown; a killed server not driven |
| 22 no server left running | met | `test_no_memory_server_outlives_axiom`; process list after live B shows none |

## Suite

1078 passed, 9 failed, 1 skipped, 1 deselected, 166 s. **The 9 failures are the baseline's:**
before any change on this branch it was 1043 passed, 9 failed (colour and rendering
assertions: `test_characterization`, `test_facts` x2, `test_indented_code`,
`test_multiline`, `test_rendering` x4). 35 tests were added; since then 4 more, 39 in
`tests/test_memory.py`, all passing. The venv in the checkout was built for the old path
`C:\Projects\axiom` and does not import `axiom`; the suite is run with `PYTHONPATH=src`.

## What the live run found (all of it on gemma4:e2b and the real Synaptra)

1. **Setup works.** 136 s on this line, no error. Venv 875 MB, model cache 175 MB. The
   plan in the first-run text said 940 and 90; changed to 875 and 175.
2. **The model supplies its own `rater`.** It wrote `rater=axiom`. The first version kept
   what the model gave; now it is always the model's name.
3. **uv also writes to its own cache** (outside the project) and `uv venv --python 3.12`
   may fetch a Python. AC 7 says nothing is written outside the folder except the model
   download. Not measured; it is probably untrue as written.
4. **Recall by meaning alone returns the right memory and cannot tell it is right.** The
   real server scored the cat memory 0.0213 for "what is my cat called?" and 0.0213 for
   "what is the weather in London". `found_by` held `semantic` and `temporal` for both.
5. **Its keyword search matches single words, not sentences.** "cat" and "Biscuit" were
   found by keyword; "what is my cat called?" was not. So the first filter (keyword and
   semantic) passed nothing, and live session 2 answered "I do not have access to your
   personal information". Fix: look up the question's content words one at a time and
   keep keyword hits. Against the real store: the cat question and "do you know where I
   live?" return the memory; weather, haiku and "my pet" return nothing. 0.1 to 0.5 s.
6. **Startup line says "server start limit 30s"** while memory's own limit is 120 s.
   Cosmetic, unfixed.

## Constraint for the next cycle

The count is 15. The seven owed rows split in two: five need only code and tests (4, 8,
14, 20, and the words of 21), two need the live pair of sessions again (10, 11) after the
recall fix, and AC 7 needs a decision the loop cannot make: either measure and amend the
criterion to name tool caches, or run the installs with `--no-cache`. That is the owner's.

## Held

Velasari asked (08:15 UTC) for nothing heavy for ~20 minutes: no Synaptra servers, torch,
suites or models. Cycle 2's first moves are code and tests only.

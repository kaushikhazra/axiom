# Observe

Record each cycle:

- A status token for **every one of #35's 30 criteria**, grouped under the issue's own
  headers: `not-started` / `attempted` / `met-with-evidence` / `blocked`. All 30 get a token
  every cycle, even "no change." Cite them as "AC 19".
- How far that moved from the last cycle, and what moved it.
- What is still missing, and whether it can be closed from here at all.
- Any assumption that changed.

## What counts as evidence

**Stubs settle most of this. They cannot settle the network.**

- **AC 16, 17, 18, 19, 20 need at least one real run each** - throttling, an unreachable
  address, an error status, a fetch that does not finish, and no network at all. A stub
  proves we handle *our idea* of a 403; only the provider proves what it actually sends.
- **AC 8, 9, 10 - independence - need to be shown, not argued.** AC 10 in particular: a
  throttled search must not prevent reading an address the user supplies. Force the failure
  rather than waiting for it.
- **Everything else may be stubbed**, and should be. Live web calls are slow, rate-limited,
  and make a suite that cannot run offline.
- **No test in the suite may require the network.** The hermeticity check must keep passing.
  Live evidence belongs in cycle logs, not in the test suite.

## The tool-testing rules still bind

`CLAUDE.md`'s "Testing tools before security exists" governs this loop too. Fetching is the
capability that adds a category the file tools did not: **an arbitrary-URL fetcher will
happily request `localhost:11434`, `169.254.169.254`, or anything else on the local network.**

The security stories have not landed and this loop does not fix that. It does mean:

- **A live model is never asked to fetch an address it chose itself** during testing. Give it
  the address, or use a stub.
- Live fetches in cycle work go to stable public documentation pages, nothing else.
- If a cycle finds an SSRF-shaped hazard, **record it in the log and say so plainly** rather
  than quietly adding a filter - that is a security story's decision, not this loop's.

## The golden transcript

`tests/baseline/transcript.txt` carries 18 scenarios from #33 and #34. **This loop will
change it legitimately** - AC 1 puts web availability in the startup line.

When it does: copy the baseline aside first, regenerate with `AXIOM_WRITE_BASELINE=1`, then
**diff old against new and put the diff in the log**. Confirm every changed line is one you
meant to change. This procedure has caught a real mistake twice - once a transcript written
with machine-specific paths in it, once a scripted edit that silently did not apply.

Add scenarios for the new observable paths: a search running, a page being read, a throttled
search, an unreachable address.

## Standing checks

- **The full suite is re-run in every cycle that changes code**, and the result recorded.
- **The suite must stay green with no Ollama and no network**, and must not be changeable by
  the environment:
  `env AXIOM_HOST=http://127.0.0.1:1 AXIOM_MODEL=nonsense:99b AXIOM_DEBUG_MAX_CONTEXT=7 uv run pytest -q`
- **#33's structure and #34's seam are kept.** `ollama` and `httpx` stay inside `backend.py`;
  only `terminal.py` prints; tools are declared once with no per-model branch; tests inject
  rather than patch. Check by grep when a cycle adds a module.
- **A new dependency is allowed** - the repo rule is reuse before build - but say in the log
  what was considered and why this one, and check it does not drag in a vendor client that
  would break the `backend.py` boundary.
- If a criterion cannot be met as written, say so plainly and say why. Do not quietly
  reinterpret one to make it passable.

## Goal check

- **Met** - all 30 criteria are `met-with-evidence`, the network-facing ones from real runs,
  and the suite is green and hermetic. The loop ends.
- **Not met** - report which criteria moved and which did not, and write the next action.
- **Answer did not move** - report the flat result and stop. Do not run another variant.

# Action

Find out what the libraries actually do, then say where search and fetch fit. **Write no
production code this cycle.**

#34's pattern held every time it was followed: probe first, design second. The one decision
reasoned from the code rather than probed turned out to be wrong.

## Probe the search side

`assumption.md` says the library is `ddgs`, renamed from `duckduckgo-search`. **Confirm
that** - check the current package name, whether it is maintained, and what its API looks
like now. Do not trust the note; it was written from a web search, not from the package.

Then, with **a handful of searches, not a loop of them**:

- What a result actually contains - title, address, snippet, anything else (AC 3).
- Whether the count is controllable, and what its default is (AC 4).
- **What throttling looks like when it happens** - the exception type, the message, whether
  it is distinguishable from a network failure. AC 16 turns on telling those apart, and
  guessing at the shape would produce a handler that never fires. If throttling does not
  occur naturally, say so rather than forcing it - burning the IP would cost the next several
  cycles.

## Probe the fetch side

- What is available for turning HTML into readable text (AC 6). `httpx` is already here for
  the transport. Say what was considered and why - reuse before build.
- What a page with no readable text produces (AC 14).
- What an error status looks like coming back (AC 18).

**Live fetches go to stable public documentation pages only.** Nothing else, and never an
address a model chose.

## Then check what is already done

`assumption.md` notes that #34's machinery may already satisfy several criteria. Walk them
and say which:

- AC 13, 14, 15 - visibility. `note_tool` and `show_tool_result` already exist.
- AC 21 - Ctrl-C during a fetch. The turn loop already handles interrupts; `run_command`
  needed extra work because it held a subprocess. Does a fetch?
- AC 25, 26 - configuration. `Limits` already exists and `--no-tools` already switches tools
  off. Does AC 26 need anything new, or is it already true?

Criteria already met by existing work should be recorded as such with evidence, not rebuilt.

## Then name the shape

Where search and fetch live, what `Limits` gains, and - the one real design question -
**how the two stay independent under AC 10.** A throttled search must not prevent a fetch.
Say what makes that structurally true rather than incidentally true.

## Record

Baseline: `wc -l` across `src/`, the test count, and the hermeticity check. Note which of the
18 transcript scenarios will change when the startup line gains web availability, and which
new observable paths need scenarios.

All 30 criteria get a status token. Most will be `not-started`; the point is the probe
results and the list of what is already true.

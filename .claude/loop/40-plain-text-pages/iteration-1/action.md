# Action

**Cycle 1 writes no production code.** Measure what is actually true, record the baseline
the preservation criteria will be judged against, and settle the two contradictions. A fix
designed against an imagined failure is a fix for the wrong thing - that is why #32 spent
its first cycle this way and why its second cycle overturned the plan.

## 1. Probe the library

One short script in `.tmp/`, not a test. Call `trafilatura.extract` directly on bodies you
construct and record the exact return value for each:

- a plain-text body with indentation and blank lines
- a markdown body
- a csv body
- a javascript body
- an empty string
- an HTML body with real prose, as the control

Record what came back verbatim - `None`, `''`, or text. If any of these returns usable text,
the shape of the fix changes, so measure rather than assume.

## 2. Probe what real servers actually send

The branch this fix keys on is `Content-Type`, so record what real ones look like. Fetch
each and record the exact header, the status, and the first line of the body:

- a raw source file (`raw.githubusercontent.com`)
- a README served raw
- a `robots.txt`
- a licence file
- a PDF
- an image
- something serving no `Content-Type` at all, if one can be found

Note charset suffixes, casing, and whitespace exactly as they arrive. AC 3 names markdown,
rst, csv and javascript specifically - find out what types those are really served as,
because "text/*" may not cover all of them and `application/json` and
`application/javascript` are the obvious traps.

## 3. Record the baseline

- Full suite and the hermeticity check. Confirm 193 green.
- Copy `tests/baseline/transcript.txt` aside so a later diff is a command, not a memory.
- Run the four AC 12 failures as they behave **today** and record their exact messages:
  unreachable address, error status, fetch past the time limit, cancelled fetch. These are
  the strings AC 12 says must not change.
- Record today's behaviour for a plain-text page and for a PDF, so the before/after is on
  the record rather than described.

## 4. Find the seam for the third state

The three outcomes are decided and recorded in `assumption.md`. What is **not** decided is
how the middle one travels, and that is a code question, not a judgement call.

`__init__.py` decides a source with `not result.startswith("error:")`. An empty page must
reach the user as a warning, must not be an error, and must not be a source - which that
single test cannot express. Read the call site and say what the smallest honest change is.
Options worth weighing, in one line each: a second recognised prefix; `fetch_page` returning
something richer than a bare string; or the source decision moving out of `__init__.py` and
into `tools.py` where the outcome is actually known.

Weigh them against #43, which will add tools from MCP servers whose results axiom does not
author. A source rule that only works for strings axiom wrote itself is a rule that breaks
in two loops' time. Recommend one and say what it costs.

## 5. Say what the fix will be

One paragraph, no code. Which branch goes where in `fetch_page`, what decides text from
not-text given that a missing type now means text, and how each of the three outcomes leaves
the function. If the probes show the obvious fix is wrong, say that instead - that is a
better cycle 1 than a plan that survives because nothing tested it.

## Record

Status for all 12 criteria - most will read `not-started`, and that is the correct result
for this cycle. AC 12's four behaviours get their baseline strings recorded, which makes
them `attempted` at best, not met. Then write cycle 2's `action.md`.

**Write no questions into it.** If cycle 1 turns up something ambiguous, decide it, record
the decision and the reasoning in the log, and carry on - see `observe.md`. Nobody is
reading between firings.

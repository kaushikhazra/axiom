# Cycle 2 - 2026-08-25 08:37 IST

Both tools built and tested. **150 tests green, from 131.** `src/` 1021 -> 1116.

## A contradiction in the action, resolved

Cycle 1's action asked for the startup line to name web availability **and** said not to
regenerate the transcript. Those cannot both hold - every scenario opens with that line.

Resolved by deferring the startup line and the web switch to cycle 3, and doing the tools,
`Limits` and tests here. That is the order #34 used: mechanism first, startup line as its own
headline. It also keeps the transcript a live safety net through the cycle that adds the most
code.

## The dependency decision, confirmed

`ddgs` and `trafilatura` added. Cycle 1 recorded the cost - 17 and 18 packages - and asked
this cycle to confirm or overturn it rather than inherit it.

**Confirmed.** DuckDuckGo has no official API; hand-rolling a scraper is the wheel the repo
rule exists to stop. And the stdlib alternative for extraction would satisfy "markup
stripped" while failing "navigation stripped", which AC 6 asks for by name. The live check
below is what a hand-rolled stripper would have to match.

## The two tools

Two ordinary entries in `tools.REGISTRY`, riding #34's mechanism. `Limits` gains
`search_results`, `fetch_timeout` and `page_characters` - operational, and a test asserts
none of them appear in either tool's schema, so a model cannot set them by asking.

Each of cycle 1's three findings is handled where it bites:

- **The status is checked explicitly.** httpx does not raise on 4xx, and a 404's body extracts
  into convincing prose. `test_an_error_status_is_reported_as_that_error` feeds a 404 whose
  body is plausible content and asserts that content does **not** come back - the failure it
  guards against is answering from an error page, which is worse than the empty page AC 21
  names.
- **The cut is in the tool.** `page_characters` bounds what the model receives, and says by
  how much it was cut. #34's display truncation is untouched and remains a separate concern.
- **Throttling has its own message.** `RatelimitException` becomes "throttling us - wait and
  retry"; a timeout and an unreachable provider do not. Two tests assert the other two are
  *not* reported as throttling, because the advice differs - one is wait, the other is check
  the network.

## AC 10, forced rather than argued

Cycle 1 said independence was structural. Two tests now make it observable: a throttled
search followed by a successful fetch, and an unreachable page followed by a successful
search.

That matters more than it looks. DuckDuckGo throttling is routine, and a design where one 202
took away the ability to read an address the user handed over would disable half the feature
on a normal day.

## The transcript, regenerated

Registering two tools changed `5 tools` to `7 tools` - a real observable change, caught by
the transcript rather than noticed later.

Copied aside first, then diffed. Every changed line, summarised:

```
14 x  (context: 32768 tokens, 5 tools)          -> 7 tools
 1 x  (context: 200 tokens, debug override, 5..) -> 7 tools
```

Fifteen lines, all startup lines, all the same substitution. The three scenarios whose
startup line says `tools off` or `no tools` are untouched, which is right - neither depends
on the count.

## Live check

Real providers, one search and one fetch, stable documentation only:

```
pathlib - Object-oriented filesystem paths - Python 3.14.7 documentation
https://docs.python.org/3/library/pathlib.html
3.14.7 Documentation ... This module offers classes representing filesystem paths...
---
pathlib - Object-oriented filesystem paths
Added in version 3.4.
...
[cut here - 54024 more characters not included]
```

The cut message confirms cycle 1's measurement exactly: 54,324 characters extracted, 300
kept, 54,024 withheld.

## Criteria status

**Startup** 1 `not-started` - deferred to cycle 3 with the web switch

**Searching**
2. `attempted` - the tool works live; answering *from* what it finds needs a model
3. `met-with-evidence` - title, address and snippet, tested and seen live
4. `met-with-evidence` - default honoured, override honoured

**Reading a page**
5. `attempted` - fetches and returns content; answering from it needs a model
6. `met-with-evidence` - markup and navigation gone, tested and seen live
7. `not-started` - needs a live model doing both in one turn

**Independent** 8-9 `not-started` - need a model choosing; 10 `met-with-evidence`

**Sources** 11-12 `not-started` - both are about what a model does with what it read

**Visibility** 13-15 `not-started` - `note_tool` and `show_tool_result` should cover these,
but neither has run against these tools yet

**Boundaries** 16 `met-with-evidence`, 17 `met-with-evidence`, 18 `met-with-evidence`

**Failure and recovery** 19 `met-with-evidence`, 20 `met-with-evidence`,
21 `met-with-evidence`, 22 `met-with-evidence`, 23 `not-started` - no-network is not the same
as unreachable-host and wants its own check, 24 `not-started`

**State** 25-26 `not-started`

**Configuration** 27 `met-with-evidence` - no key, no account, seen live;
28 `attempted` - the three exist in `Limits` but are not yet wired to flags and environment;
29 `not-started`

**Exit** 30 `not-started` - unchanged, but not re-verified since the tools were added

## Goal check

**Not met.** 13 of 30 carry evidence, from 0.

## What is left

Three groups:

- **Configuration and the startup line** - AC 1, 28, 29. One cycle, ending in a deliberate
  transcript regeneration.
- **Things only a model can demonstrate** - AC 2, 5, 7, 8, 9, 11, 12. A live cycle, and AC 12
  is the interesting one: axiom must not cite an address it did not read, which is a claim
  about the model's behaviour that a prompt may have to support.
- **The rest of the plumbing** - AC 13, 14, 15, 23, 24, 25, 26, 30. Mostly re-verification of
  #34 machinery against these tools, plus a real no-network check.

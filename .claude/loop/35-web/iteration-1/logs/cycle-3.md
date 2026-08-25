# Cycle 3 - 2026-08-25 08:52 IST

Configuration, the startup line, the plumbing verified, and a deliberate transcript
regeneration. **166 tests green, from 150.** `src/` 1116 -> 1189.

## Two switches, composed obviously

`--no-web` switches off searching and fetching and leaves the other five tools alone.
`--no-tools` switches off everything, web included.

```python
web_enabled = not args.no_web and not args.no_tools
```

The alternative - tools off but web on - would have been the clever answer and nobody would
expect it. Four tests pin the composition, including both flags together, so a later change
has to break a named expectation rather than drift.

Live:

```
$ axiom --no-web
axiom: qwen2.5:7b at http://localhost:11434 (context: 32768 tokens, 5 tools, web off)
```

Five tools, not seven, and the file tools survived.

## The startup line, without a matrix

Three tool states and three web states is nine sentences if written carelessly. It stays four
because **the web state only means anything when tools are available**:

| | |
|---|---|
| `7 tools including web` | AC 1 |
| `5 tools, web off` | AC 29 |
| `tools off` | web is not mentioned - there is nothing true to say |
| `no tools - this model cannot call them` | same |

A test asserts the word "web" does not appear in either of the last two.

## Web tools filtered without weakening #34's guard

`declarations()` still takes no arguments - #34 has a test asserting that with
`inspect.signature`, put there to stop a per-model parameter appearing. Adding a `web` flag
to it would have passed review and quietly deleted that guard.

Instead `tools.WEB_TOOLS` names the two, and `main()` filters. The caller decides what to
offer; `tools.py` still declares one fixed set.

## The plumbing: verified, not assumed

Cycle 1 predicted six criteria would fall out of #34's machinery. Each now has a test driving
these tools rather than an argument that it should work:

- **AC 13** - `search_web(query=teal cats)` appears before the search runs.
- **AC 14** - `fetch_page(url=...)` appears before the fetch.
- **AC 15** - fetched content carries the `  |` marker and the model's own words do not.
- **AC 25** - the page reaches history as a `tool` message tagged `fetch_page`.
- **AC 26** - **the address survives compaction.** This is the one worth having: the criterion
  names addresses specifically, and it only holds because #34 cycle 6 made compaction render a
  call's arguments. Without that a summary would record what a page said and not which page -
  and the test would have caught it.

All six passed first time. The prediction was right; it is now evidence rather than a
prediction.

## AC 23: no network, forced

Both tools fail plainly with the network gone. **The half that matters is the other half**:
chat still answers, because Ollama is local and losing the internet should cost the web and
nothing else. A session that stopped answering arithmetic because DuckDuckGo was unreachable
would be broken in a way the user cannot diagnose.

## The regeneration, diffed

Copied aside first. Then, rather than reading the diff by eye:

```
$ diff old new | grep "^<" | grep -vc "axiom: qwen2.5:7b at"
0
```

**Zero removed lines that are not startup lines.** Everything else in the diff is an
addition: five new scenarios - a search, a throttled search, a page read, an unreachable
address, and the web switched off - plus `7 tools` becoming `7 tools including web` on the
eighteen that already existed.

The harness needed stubbing for this. It drives the *real* tools, so a search scenario would
have reached DuckDuckGo and a fetch scenario whatever address it named - neither repeatable
nor allowed in a suite that must run offline. The stubs are keyed on the input, so
`throttle me` throttles and `unreachable.invalid` refuses, and each scenario gets the case
its name promises.

## Criteria status

**Startup** 1 `met-with-evidence`

**Searching** 2 `attempted`, 3-4 `met-with-evidence`

**Reading a page** 5 `attempted`, 6 `met-with-evidence`, 7 `not-started`

**Independent** 8-9 `not-started`, 10 `met-with-evidence`

**Sources** 11-12 `not-started`

**Visibility** 13-15 `met-with-evidence`

**Boundaries** 16-18 `met-with-evidence`

**Failure and recovery** 19-23 `met-with-evidence`, 24 `not-started`

**State** 25-26 `met-with-evidence`

**Configuration** 27-29 `met-with-evidence`

**Exit** 30 `met-with-evidence` - all four exits in the transcript, after searches and
fetches have run

## Goal check

**Not met.** 24 of 30 carry evidence, from 13.

## What is left

Six, and five of them are one job:

- **AC 2, 5, 7, 8, 9, 11, 12** - what only a live model can demonstrate. Searching and
  answering from results; reading and answering from a page; both in one flow; reading an
  address without searching; answering from snippets without fetching; naming sources.
- **AC 24** - Ctrl-C during a search or fetch. Small, and it needs the same treatment #34's
  timeout got: test the world, not the message. httpx holds a socket rather than a
  subprocess, so there may be nothing to clean up - but that is a claim to check, not assume.

**AC 12 is the interesting one.** *Axiom does not present an address as a source unless it
actually read that page* is a claim about the model's behaviour, not the code's. A model given
search snippets can easily cite a page it never fetched. If it does, the honest options are a
prompt that says not to, or an amendment to the criterion - and the log should say which,
rather than declaring it met because it happened not to misbehave in one run.

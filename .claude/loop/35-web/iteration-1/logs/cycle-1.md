# Cycle 1 - 2026-08-25 08:22 IST

Probe cycle. **No production code.** Libraries confirmed against the packages rather than
against notes, and a walk of which criteria #34's machinery already satisfies.

Baseline: `src/` **1021 lines**, **131 tests** green and hermetic, **18 transcript scenarios**.

## Search: `ddgs` confirmed

Version **9.15.0**, exports `DDGS`, with `text`, `news`, `images`, `videos`, `books`.

```python
DDGS().text("python pathlib documentation", max_results=3)
-> [{"title": ..., "href": ..., "body": ...}, ...]
```

`title`, `href`, `body` map onto **AC 3** exactly - title, address, snippet - with nothing
missing and nothing to invent. `max_results` gives **AC 4** directly.

### Throttling, without provoking it

`ddgs.exceptions` carries `DDGSException`, with **`RatelimitException`** and
`TimeoutException` under it.

That settles **AC 19** without a single wasted search: throttling is distinguishable **by
type**, not by parsing a message, and it sits in a family separate from anything a network
failure would raise. The action warned against forcing throttling because burning the IP
would cost several cycles; it turned out not to be necessary.

## Fetch: `httpx` plus something for the text

Transport needs nothing new - `httpx` is already a dependency for the backend.

For **AC 6**, `trafilatura` was probed against a real page:

| | |
|---|---|
| raw HTML | 266,554 chars |
| extracted text | 54,324 chars |
| head | `pathlib — Object-oriented filesystem paths¶ Added in version 3.4. ...` |

Navigation and markup gone, prose intact. A five-to-one reduction before anything else
truncates.

**No readable text (AC 17)**, probed directly: empty HTML and script-only HTML both extract
to `None`. A nav-only page extracts to `'Home'` - so a page that is *only* navigation does
yield its link text rather than nothing. Worth knowing; not obviously wrong.

## Three findings that change the design

### 1. httpx does not raise on an error status

A 404 came back as `status_code == 404` with a **9,511-character HTML error page** in the
body, and no exception.

Returned naively, `trafilatura` would extract that error page into plausible prose and hand
it to the model as the page's content. **AC 21 says an error status is reported as that
error, not as an empty page** - and the real hazard is worse than an empty page: it is
convincing wrong content. The status has to be checked explicitly.

### 2. AC 18 is about what the model gets, not what the screen shows

`terminal.show_tool_result` already truncates at 2000 characters and says how much was
withheld. #34 deliberately proved that this is a **screen** concern and the model still
receives the whole result - shortening what the model is told would silently change its
answer.

That was right for a file. It is wrong for a 54,000-character web page: unbounded, it would
crowd out the conversation and then trigger compaction. **AC 18's "cut to a bounded amount"
has to happen in the tool**, and the existing display truncation is a separate thing that
stays.

### 3. `--no-tools` is not `--no-web`

**AC 29** asks that *web access* can be switched off. #34 gives `--no-tools`, which switches
off all five file and command tools too. Switching off the web should not take away
`read_file`.

Related: **AC 1** asks that the startup line shows *web access* is available. Today it says
`5 tools`; with two more it would say `7 tools`, which does not say the web is reachable and
could not distinguish web-off from tools-off. The line needs to name the web separately.

## What #34 already gives, and should not be rebuilt

| criterion | already satisfied by | needs |
|---|---|---|
| 13, 14 | `note_tool` prints the call and its arguments before running | nothing - falls out when the tools exist |
| 15 | `show_tool_result` marks every line with `  \|` | nothing |
| 24 | the turn loop catches `KeyboardInterrupt` around the whole turn | checking: `run_command` needed extra work because it held a subprocess; a fetch holds a socket, and whether httpx leaves anything behind is unverified |
| 25 | tool results already enter history as `tool` messages | nothing |
| 26 | #34 cycle 6 fixed compaction over tool history - calls are rendered with their arguments, boundaries are respected | a test that the *address* survives, since that is what AC 26 names |
| 30 | unchanged by adding tools | re-verification only |

**Search and fetch are two more entries in `tools.REGISTRY`.** The visibility, truncation,
failure reporting, history handling and multi-round loop all exist and are tested. This loop
adds tools; it does not build a second mechanism.

## The shape

| where | what |
|---|---|
| `tools.py` | `search_web(query)` and `fetch_page(url)`, two more registry entries |
| `Limits` | result count, fetch timeout, and the page-content cap - operational, never model-visible |
| `config.Settings` | those three, plus a web switch distinct from `--no-tools` |
| `terminal.announce` | the startup line names web availability separately from the tool count |

**AC 10 - independence - is structural, not incidental.** Two separate registry entries with
no shared state and no call path between them: `fetch_page` never consults search, and
`search_web` never fetches. A throttled search raises inside one tool, is caught by
`tools.run`, and returns a message; the other tool is untouched because it was never
involved. Nothing needs to be built for that to be true, but the log should say so and a test
should force it rather than assume it.

## Dependency weight - worth a decision

`ddgs` installed **17 packages**; `trafilatura` installed **18**. For a project whose README
begins "Minimal agent", that is a real cost and should be a conscious choice rather than a
side effect.

Both earn it under reuse-before-build: DuckDuckGo has no official API and scraping it by hand
is exactly the wheel the repo rule says not to rebuild, and content extraction is a genuinely
hard problem that `trafilatura` is purpose-built for. The alternative for extraction - a
stdlib `html.parser` tag-stripper in about thirty lines - would satisfy "markup stripped" but
not "navigation stripped", which AC 6 asks for by name.

Recorded here so the next cycle can confirm or overturn it deliberately.

## Criteria status

All 30 `not-started` - nothing is built. Six are expected to fall out of existing work
(13, 14, 15, 24, 25, 30) and are marked `not-started` rather than claimed, because a
criterion satisfied by a mechanism that has never run against these tools is not evidenced.

**Startup** 1 · **Searching** 2-4 · **Reading** 5-7 · **Independent** 8-10 · **Sources**
11-12 · **Visibility** 13-15 · **Boundaries** 16-18 · **Failure and recovery** 19-24 ·
**State** 25-26 · **Configuration** 27-29 · **Exit** 30 - all `not-started`.

## Goal check

**Not met.** Correct for a probe cycle.

## Transcript

All 18 scenarios start with the startup line, which AC 1 changes. That is a legitimate
regeneration when it comes. New observable paths needing scenarios: a search running, a page
being read, a throttled search, an unreachable address, and web switched off.

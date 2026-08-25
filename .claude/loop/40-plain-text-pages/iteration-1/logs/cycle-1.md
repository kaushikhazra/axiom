# Cycle 1 — 2026-08-26, 01:13 IST

No production code, per `loop.md`. Measurement, baseline, and the seam for the third state.

## Criteria status

| AC | what it asks | status |
|---|---|---|
| 1 | `text/plain` returns its contents | `not-started` |
| 2 | contents as served, indentation and line breaks intact | `not-started` |
| 3 | markdown, rst, csv, javascript treated the same | `not-started` |
| 4 | HTML still reduced to readable text | `attempted` — baseline recorded, control passes |
| 5 | HTML with no readable text still reported as having none | `attempted` — baseline recorded |
| 6 | non-text reported not readable, bytes never returned | `not-started` |
| 7 | no type announced → judged by content | `not-started` — decision given, see below |
| 8 | empty page reported empty, not a failure | `not-started` |
| 9 | plain text cut to the same bound, and says so | `not-started` |
| 10 | a page read successfully is named as a source | `not-started` |
| 11 | a page not readable is never named as read | `not-started` |
| 12 | every existing failure unchanged | `attempted` — all four strings recorded |

## 1. What `trafilatura.extract` actually returns

`.tmp/probe_extract.py`. Six bodies, direct calls, no network.

| body | returned |
|---|---|
| plain text, indented | `None` |
| markdown | `None` |
| csv | `None` |
| javascript | `None` |
| empty string | `None` |
| HTML with prose (control) | `str`, 187 chars |

**The belief held.** `extract` is an HTML extractor and returns `None` for everything else,
empty string included.

**One thing measured that was not expected, and it matters.** The HTML control did not
return its input: two `<p>` elements came back joined into a single line, and the `<nav>`
was dropped. `extract` is **lossy by design** — correct for HTML, where markup is not
content, and wrong for text, where the line breaks *are* the content. So AC 2 could not be
met by coaxing text through `extract` even if it returned something. Text has to bypass it
entirely. That closes off the cheapest-looking fix before it was tried.

## 2. What real servers actually send

`.tmp/probe_types.py`. Eleven addresses, real network.

| what | `Content-Type` as it arrived | today |
|---|---|---|
| raw `.py` | `text/plain; charset=utf-8` | `error: … has no readable text` |
| raw `.md` | `text/plain; charset=utf-8` | `error: … has no readable text` |
| `robots.txt` | `text/plain` | `error: … has no readable text` |
| raw `LICENSE` | `text/plain; charset=utf-8` | `error: … has no readable text` |
| raw `.rst` | `text/plain; charset=utf-8` | `error: … has no readable text` |
| raw `.js` | `text/plain; charset=utf-8` | `error: … has no readable text` |
| raw `.csv` | `text/plain; charset=utf-8` | `error: … has no readable text` |
| raw `.toml` | `text/plain; charset=utf-8` | `error: … has no readable text` |
| PDF | `application/pdf; qs=0.001` | `error: … has no readable text` |
| PNG | `image/png` | `error: … has no readable text` |
| `example.com` (control) | `text/html` | readable text, correct |

**Eight of eight text pages fail.** The bug is not an edge case.

Four findings that change the fix:

- **AC 3's four named types are all served as `text/plain` from raw hosts.** Markdown, rst,
  csv and javascript arrive identically. The `application/javascript` trap `action.md`
  warned about does not appear on `raw.githubusercontent.com` — but it will on other hosts,
  so the rule still needs to cover text-ish `application/*` types rather than only `text/*`.
- **`robots.txt` sends a bare `text/plain` with no charset parameter.** A parser that
  assumes a `;` is present breaks on it.
- **The PDF sends `application/pdf; qs=0.001`.** A parameter on a *binary* type. Any
  equality test against `"application/pdf"` fails here. The type must be split on `;`,
  first field taken, stripped, and lowercased before anything compares it.
- **A plain-text page and a PDF are indistinguishable today** — byte-identical message
  shape. #40 is precisely the work of splitting one message into three outcomes.

**AC 6's danger is confirmed, not theoretical.** `page.text` on the PNG returned
`'�PNG\r\n\x1a\n\x00\x00\x00\rIHDR…'` — control characters, no exception. On the PDF it
returned `'%PDF-1.4\n%äüöß…'`, which looks enough like text to pass a careless eye. Either
would enter the conversation as content if the type were not checked first.

## 3. Baseline

- **Suite: 193 passed**, under the hermeticity environment
  (`AXIOM_HOST=http://127.0.0.1:1 AXIOM_MODEL=nonsense:99b AXIOM_DEBUG_MAX_CONTEXT=7`).
- **Golden transcript copied** to `.tmp/transcript-baseline-cycle1.txt`, so a later check is
  a diff command rather than a memory.
- **The four AC 12 strings, exactly as they are today** (`.tmp/probe_ac12.py`):

```
unreachable   error: could not reach https://gone.invalid/x ([Errno 11001] getaddrinfo failed)
error status  error: https://example.com/definitely-not-here answered 404
time limit    error: https://example.com/ did not answer within 0.001 seconds
cancelled     KeyboardInterrupt propagates, not swallowed
```

All three string forms begin `error:`. The cancelled case raises rather than returning, and
`__init__.py` unwinds the turn — that path is untouched by this issue.

## 4. The seam for the third state

`__init__.py` decides a source with one test:

```python
if call.name == "fetch_page" and not result.startswith("error:"):
    read.append(str(call.arguments.get("url")))
```

**A correction to this cycle's own `action.md`.** It argued the seam should be weighed
against #43, because "a source rule that only works for strings axiom wrote itself breaks
once MCP servers supply results." That reasoning is wrong and I am not going to build on it:
the test is already gated on `call.name == "fetch_page"`, so a tool axiom did not author
never reaches it. #43 does not pressure this decision. What #43 *does* touch is the broader
`error:` convention inside `tools.run()` — an MCP result carrying `is_error=True` will have
to map onto it — but that is #43's problem and does not need solving here. Deciding this on
a false constraint would have bought structure nothing was asking for.

Weighed on its own merits:

- **A second recognised prefix.** One tuple in the existing test. Cheapest, but leaves two
  string literals in `__init__.py` that only `tools.py` knows the meaning of.
- **A richer return type from `fetch_page`.** `Tool.run` is declared `Callable[..., str]`
  and every tool returns a string; the tool message is built straight from it. Changing that
  ripples through seven tools and the message construction to serve one case. Unearned.
- **Move the decision into `tools.py`.** The knowledge of which results mean "not a source"
  lives beside the code that writes them.

**Decision: the third and the first together.** Add a `warning:` prefix for the empty case,
and put the source test in `tools.py` as a named function beside the code that writes those
prefixes, called from `__init__.py`.

The precedent is in the same file and is explicit. `addresses_in()` carries this comment:
*"Parser and format live together deliberately; splitting them is how one drifts from the
other."* The prefix vocabulary is exactly that shape — a format `tools.py` writes and
`__init__.py` currently re-parses from literals. Cost: one new function in `tools.py`, one
line changed in `__init__.py`. No new types, no new dependency.

## 5. What the fix will be

`fetch_page` keeps its shape: `httpx.get` unchanged, the `status_code >= 400` guard
unchanged and still first, so AC 12 is untouched. After it, read
`page.headers.get("content-type")`, take the part before any `;`, strip it, lowercase it —
which handles both `text/plain` bare and `application/pdf; qs=0.001`. A missing or blank
header is treated as text, per the decision in `assumption.md`.

Then three ways out, and the type decides which **before anything touches `page.text`**:

- **HTML** (`text/html`, `application/xhtml+xml`) — today's path exactly:
  `trafilatura.extract`, and the existing "no readable text" message when it returns None.
  AC 4 and AC 5 are preserved by not moving this.
- **Text** (anything else under `text/`, the text-ish `application/*` types, or no header at
  all) — `page.text` verbatim, no extraction, so indentation and line breaks survive as AC 2
  requires. The `page_characters` cut and its existing `[cut here - N more characters not
  included]` message apply unchanged, which is AC 9.
- **Not text** (everything else) — `error:` naming the type, and `page.text` is never
  accessed at all. Not a truncated copy, not a decoded approximation. AC 6, AC 11.

Empty splits along a line that keeps AC 5 and AC 8 both true: a body that is empty or only
whitespace returns `warning: … is empty` — not an error, not a source. An HTML body that
has content but no extractable prose keeps today's `error: … has no readable text`, because
that is what AC 5 asks for and it is a different thing from an empty page.

## What is still missing

Everything except the baseline. No production code exists yet. Cycle 2 writes the
classifier and the three outcomes; cycle 3 covers sources and the cut.

Nothing is blocked, and nothing here needs an answer from Kaushik.

## Assumptions that changed

One added, from the measurement: **`trafilatura.extract` is lossy on its own control
input** — it joins paragraphs and drops chrome. Recorded in `assumption.md`, because a later
cycle tempted to route text through `extract` "just to normalise it" would silently fail
AC 2, and the failure would look like a formatting nit rather than a criterion.

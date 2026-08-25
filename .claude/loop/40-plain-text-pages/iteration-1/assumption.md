# Assumption

Standing inputs. These are given - do not re-derive them, and do not spend a cycle deciding
them.

## The codebase this lands in

#33, #34, #35 and #32 all merged. `src/axiom/` is seven modules and 1416 lines; **193
tests, green and hermetic** at scaffold time.

- **`fetch_page` in `tools.py` is where this lives.** It is about thirty lines and its
  order matters: `httpx.get(url, timeout=..., follow_redirects=True)`, then the
  `status_code >= 400` guard, then `trafilatura.extract(page.text)`, then the
  `page_characters` cut.
- **`trafilatura.extract` is an HTML extractor.** Handed a plain-text body it returns None,
  which falls into the `if not text` branch and becomes
  `error: {url} has no readable text`. **That is the whole bug.** It is not a
  configuration of trafilatura that was missed - it is the wrong tool for a body that is
  already text. Measured in cycle 1 across six body types: plain text, markdown, csv,
  javascript and the empty string all return `None`.
- **`trafilatura.extract` is also lossy on the input it is right for** (cycle 1). The HTML
  control came back with two `<p>` elements joined into one line and the `<nav>` dropped.
  That is correct for HTML, where markup is not content, and **wrong for text, where the
  line breaks are the content**. So AC 2 cannot be met by routing text through `extract` -
  not even "just to normalise it". Text bypasses it entirely.
- **Content types arrive with parameters, and sometimes without.** Measured against real
  servers in cycle 1: `text/plain; charset=utf-8` from raw hosts, a bare `text/plain` from
  `python.org/robots.txt`, and **`application/pdf; qs=0.001`** - a parameter on a binary
  type, which defeats any equality test. Split on `;`, take the first field, strip,
  lowercase, then compare. Raw hosts serve markdown, rst, csv and javascript all as
  `text/plain`, but other hosts will not, so the rule covers text-ish `application/*` types
  as well as `text/*`.
- **The `error:` prefix is the sources contract.** `__init__.py` appends to `read` when a
  `fetch_page` result does not start with `error:`, and `terminal.show_sources(read, seen)`
  prints it. There is no other channel. AC 10 and AC 11 are settled through this prefix and
  nothing else, which is why AC 8's "empty is not a failure" collides with it.
- **`page.text` decodes bytes using the charset in `Content-Type`**, falling back to
  detection. It never raises on binary - it returns mojibake. AC 2 (content as served,
  indentation and line breaks intact) and AC 6 (bytes never returned as content) both
  depend on understanding this.
- **`page_characters` defaults to 20,000**, set by `--page-characters` or
  `$AXIOM_PAGE_CHARACTERS`. AC 9 says a plain-text page is cut to the same bound and says
  so; the existing cut message is
  `[cut here - N more characters not included]`.
- **`terminal.py` owns every print.** Nothing else in the codebase writes to stdout.
- **`tests/conftest.py`** holds `StubBackend`, `feed()`, `chunk()`, `vendor_call()` and the
  autouse fixture clearing `AXIOM_HOST`, `AXIOM_MODEL` and `AXIOM_DEBUG_MAX_CONTEXT`. If a
  suite suddenly fails on the startup line, that fixture has been lost - restore it rather
  than working around it.
- **`tests/test_web.py` already covers the HTML paths**, including the four failures AC 12
  protects: unreachable address, error status, fetch past the time limit, cancelled fetch.
  Those tests are the AC 12 evidence if they still pass unchanged.
- **`httpx.Response(status, text=...)` stamps `content-type: text/plain; charset=utf-8`**
  (cycle 2). Every HTML stub in the suite was built that way, so for as long as `fetch_page`
  ignored the header they were announcing plain text while serving markup - and the suite
  could not have caught a content-type mistake in either direction. `given_page` and
  `stub_fetch` now set the header explicitly. **Any new stubbed response must say its type**,
  or it is testing a contradiction.

## Decided by Kaushik - do not reopen

Three questions this scaffold originally left to cycle 1. All three are settled. Implement
them; do not spend a cycle re-deciding them.

- **AC 7 - a page announcing no type at all is treated as text.** Not as HTML, and not as
  unreadable. The reason is not code execution - `trafilatura` parses HTML, it does not run
  it - but that treating an unknown body as text is lossless and predictable, where routing
  it through an HTML extractor reshapes it or returns None. Text is the conservative
  default: it can only ever hand back what was served.
- **AC 8 - an empty page is a warning.** Not an error, and **not a source**. The user is
  told plainly that the page is empty. This is a third state, and the codebase has only two
  today: the `error:` prefix is the sole signal, and `__init__.py` appends to `read`
  whenever a result lacks it. **That mechanism has to grow a third case** - empty is
  neither an error nor a source. Whatever carries it, `terminal.py` still owns the printing
  and the sources list still excludes it.
- **AC 6 - a page that is not readable hands the model none of its content.** Not a
  truncated copy, not a decoded approximation, not a byte. The model is still told the page
  could not be read, because that is what stops it answering from memory and is what AC 6
  says - but the page's own content does not enter the conversation at any size. If this
  turns out to break something downstream, that is handled case by case when it happens;
  do not pre-emptively soften it.

## Given

- **`requires-python = ">=3.12"`; the venv is 3.14.3.** `uv` and pytest.
- **Dependencies are `ollama`, `httpx`, `psutil`, `ddgs`, `trafilatura`.** A new one needs
  a stated reason - and content-type handling almost certainly needs none, since httpx
  already parses the header. Reach for a library over hand-rolling, but not for a header
  lookup.
- **`axiom:main` stays the packaging entry point.**
- **The repo's own rules apply**: KISS over structure, one command per shell invocation,
  nothing committed under a `temp` name, project-local `.tmp/` for anything durable, loop
  files stay in this folder while code stays in `src/` and `tests/`.
- **The branch is `feature/40-plain-text-pages`.** Commits reference #40.
- **#40 is row 5 of four queued rows.** #41, #42 and #43 follow. #41 changes what the model
  is told about page limits and #43 adds a new tool source, so leave `fetch_page`'s shape
  intact where the criteria do not require moving it.

## Carried forward, worth not relearning

- **Probe before designing.** Every significant decision in #34 and #35 that was probed
  first held; both hypotheses reasoned from the code alone were wrong. This issue is
  itself an instance - a library was assumed to be more general than it is.
- **A scripted `.replace()` that does not match reports success.** It has happened four
  times across this queue. Verify scripted edits landed.
- **Test the world, not the message.** #34's timeout reported "stopped it" while the
  command kept running. AC 6 is exactly this shape: assert on what the model received, not
  on what was printed.
- **A criterion can turn out to be wrong.** #35 AC 12 could not be met by asking a 7B model
  to be candid, and #32 amended three on measurement. Saying so with evidence is a result,
  not a failure.

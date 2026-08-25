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
  already text.
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

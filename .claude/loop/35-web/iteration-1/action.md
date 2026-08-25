# Action

Add the two tools. The mechanism exists; this is two registry entries and the three findings
from cycle 1.

## Add the dependencies, deliberately

`ddgs` and `trafilatura` into `pyproject.toml`. Cycle 1 recorded why each earns its place and
what it costs - 17 and 18 packages. **Confirm or overturn that judgement in this cycle's log
rather than inheriting it silently.** If overturned, say what replaces it.

## `search_web(query)`

Returns title, address and snippet per result, `max_results` from `Limits` (AC 3, AC 4).

- `ddgs.exceptions.RatelimitException` becomes a message saying the provider throttled us,
  **distinct from any other failure** (AC 19). `TimeoutException` and the `DDGSException`
  base get their own handling - do not collapse them into one.
- No results is reported as no results, not as an error (AC 16).

## `fetch_page(url)`

`httpx` for transport, `trafilatura` for text (AC 5, AC 6).

Three things cycle 1 found, each of which the obvious implementation gets wrong:

- **Check the status explicitly.** httpx does not raise on 4xx or 5xx, and a 404's body is a
  9.5KB HTML error page that extracts into convincing prose. Reporting the status is AC 21;
  returning the error page as content is the failure it exists to prevent.
- **Cut the content in the tool, not just on screen** (AC 18). A page extracts to ~54,000
  characters. The display truncation from #34 stays as it is - it is a separate concern, and
  #34 proved the model must otherwise receive results whole. Say in the tool's result that it
  was cut and by how much.
- **`trafilatura.extract` returns `None`** for a page with no readable text. That is AC 17,
  and it must read as "this page has no readable text", not as an empty string that looks
  like success.

Timeout from `Limits` (AC 22). An unreachable address raises `httpx.HTTPError` - report the
reason (AC 20).

## Configuration

`Limits` gains result count, fetch timeout and the page cap. `Settings` gains those plus a
**web switch separate from `--no-tools`** - switching off the web must not take away
`read_file` (AC 29).

Then the startup line names web availability separately from the tool count (AC 1), because
`7 tools` says nothing about whether the web is reachable and cannot distinguish web-off from
tools-off.

## Tests

Stub-driven; **no test may touch the network**. Patch `ddgs.DDGS` and `httpx.get` at the
point `tools.py` uses them.

Cover: result shape, the default count, throttling reported distinctly, no results, a 404
reported as an error rather than as content, a page with no text, a page cut with the amount
stated, an unreachable address, and a timeout.

**AC 10 gets a test that forces it**: a throttled search followed by a successful fetch in
the same session. Cycle 1 argued it is structurally true; make it observably true.

## Safety

Live checks in this cycle, if any, go to stable public documentation pages only. **A handful
of searches, not a loop.** No live model chooses an address.

## Record

Full suite and the hermeticity check. `wc -l` and test count against 1021 and 131. Status for
all 30. Do not regenerate the transcript yet - the startup line changes with the web switch,
and that deserves the cycle where it is the headline.

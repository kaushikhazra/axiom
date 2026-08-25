# Action

Write the classifier and the three outcomes. Cycle 1 measured everything this needs; the
plan is in `logs/cycle-1.md` section 5 and is not to be re-derived.

## 1. The classifier

A small function in `tools.py` that turns a response into one of three answers: HTML, text,
or not readable.

- Take `page.headers.get("content-type")`, split on `;`, first field, `.strip().lower()`.
  Cycle 1 measured all three shapes this has to survive: `text/plain; charset=utf-8`, a bare
  `text/plain`, and `application/pdf; qs=0.001`.
- **HTML**: `text/html`, `application/xhtml+xml`.
- **Text**: anything else under `text/`, plus the text-ish `application/*` types -
  `application/json`, `application/javascript`, `application/xml`, and the `+json` / `+xml`
  suffixes. Raw hosts serve markdown, rst, csv and javascript as `text/plain`, but other
  hosts will not.
- **Text**, also, when the header is missing or blank. That is Kaushik's decision in
  `assumption.md`: text is the only treatment that can hand back exactly what was served.
- **Not readable**: everything else.

Test the classifier directly on header strings, including the three measured shapes, an
absent header, an empty string, and an uppercase `TEXT/PLAIN`.

## 2. The three outcomes in `fetch_page`

Order is load-bearing. `httpx.get` and the `status_code >= 400` guard do not move - AC 12
depends on that, and cycle 1 recorded the four strings it protects.

- **HTML** - today's path unchanged: `trafilatura.extract(page.text)`, and the existing
  `error: {url} has no readable text` when it returns None. AC 4 and AC 5 are preserved by
  not touching this branch.
- **Text** - `page.text` verbatim. No extraction. Indentation and line breaks survive,
  which is AC 2. Then the existing `page_characters` cut with its existing
  `[cut here - N more characters not included]` message, which is AC 9.
- **Not readable** - return an `error:` naming the type, and **never access `page.text`**.
  Not truncated, not decoded, not sampled. Cycle 1 confirmed `page.text` returns
  `'�PNG\r\n\x1a\n…'` for a PNG without raising, so this is a real path to guard, not a
  theoretical one.

**Empty**, across both readable branches: a body that is empty or only whitespace returns
`warning: {url} is empty`. Not an error. An HTML body that has content but no extractable
prose keeps today's `error: … has no readable text` - AC 5 and AC 8 are different cases and
stay different messages.

## 3. The source seam

Decided in cycle 1 section 4, on the precedent of `addresses_in()` in the same module:
*"Parser and format live together deliberately; splitting them is how one drifts from the
other."*

- A named function in `tools.py` answers whether a `fetch_page` result means the page was
  read. It knows about both prefixes because it sits beside the code that writes them.
- `__init__.py` calls it instead of testing `not result.startswith("error:")` itself.
- Do not widen this to other tools and do not generalise it for #43. Cycle 1 established
  that #43 does not pressure this decision - the call site is already gated on
  `call.name == "fetch_page"`.

## 4. Prove it, and prove nothing else moved

- Unit tests for each branch, with stubbed responses, asserting on **what the function
  returned** - never on what was printed. AC 6's test asserts the PNG's bytes appear nowhere
  in the result, not that the message says "not readable".
- Run the four AC 12 probes again and diff against the strings in cycle 1's log. They are
  quoted there exactly.
- Full suite and the hermeticity command. 193 is the floor; it should only grow.
- `diff` the golden transcript against `.tmp/transcript-baseline-cycle1.txt`. If it moved,
  say which lines and why, and only regenerate deliberately with `AXIOM_WRITE_BASELINE=1`.

## Record

Status for all 12. AC 1, 2, 3, 6, 7 and 9 should reach `met-with-evidence` this cycle if the
branches land; AC 8, 10 and 11 depend on the source seam and may follow in cycle 3. Then
write cycle 3's `action.md`.

**Write no questions into it.** Decide, record the decision and the reasoning in the log,
carry on. Nobody is reading between firings.

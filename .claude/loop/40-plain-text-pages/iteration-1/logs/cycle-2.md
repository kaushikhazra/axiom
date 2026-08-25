# Cycle 2 — 2026-08-26, 01:28 IST

The classifier, the three outcomes, and the source seam. All twelve criteria now have
evidence. **Convergence is not declared** — see the last section.

## Criteria status

| AC | status | evidence |
|---|---|---|
| 1 | `met-with-evidence` | real `python.org/robots.txt` returns its contents; unit test |
| 2 | `met-with-evidence` | real Apache `LICENSE` keeps its leading spaces; unit test asserts exact string equality |
| 3 | `met-with-evidence` | `.md`, `.rst`, `.js`, `.csv`, `.toml` all live; unit test over 11 type strings |
| 4 | `met-with-evidence` | golden transcript byte-identical; `example.com` control; every pre-existing HTML test passes |
| 5 | `met-with-evidence` | distinct message kept; unit test asserts "empty" is *not* in it |
| 6 | `met-with-evidence` | live PDF and PNG refused; bytes-never-returned test |
| 7 | `met-with-evidence` | a really-served typeless response over TCP; exact match |
| 8 | `met-with-evidence` | unit tests, empty body and whitespace-only body |
| 9 | `met-with-evidence` | unit test: same bound, same message as any other page |
| 10 | `met-with-evidence` | end-to-end: a plain-text page is named among the sources |
| 11 | `met-with-evidence` | end-to-end: neither an unreadable nor an empty page is named |
| 12 | `met-with-evidence` | all four strings byte-identical to cycle 1's baseline |

Suite: **223 passed** (193 + 30), hermetic. Golden transcript **unchanged and not
regenerated**.

## What was built

`tools.py` gains `_media_type` and `_treat_as`, and `fetch_page` gains three ways out. The
order is the load-bearing part: `httpx.get` and the `status_code >= 400` guard did not move,
and the type is decided **before anything touches `page.text`**.

- **HTML** — `trafilatura.extract`, unchanged, including its existing "no readable text"
  message. AC 4 and AC 5 preserved by not touching the branch.
- **Text** — `page.text` verbatim, then the existing cut. No extraction.
- **Not text** — an `error:` naming the type, and `page.text` is never accessed.

`was_read()` joins them in `tools.py`, next to `addresses_in()` and for the reason that
function already states in its own comment: parser and format live together. `__init__.py`
now asks it instead of testing `not result.startswith("error:")` itself — one line.

## The finding that mattered most, and it was in the tests

The first run after the change came back **4 failed**, three of them HTML tests that had
passed for two issues. The cause was not the new code.

`httpx.Response(200, text=...)` **stamps `content-type: text/plain; charset=utf-8`** on the
response. Every HTML test in `test_web.py`, and the characterization harness's `stub_fetch`,
built their pages that way. So for as long as `fetch_page` ignored the header, those stubs
were announcing *plain text* while serving HTML and nobody could tell.

This is worth stating plainly: **the existing suite could not have caught a content-type
mistake in either direction.** It was not testing the header, it was contradicting it. The
three failures were the new classifier correctly believing a stub that had always been
wrong.

The fix was in the stubs, not the baseline. `given_page` now takes `content_type`,
defaulting to `text/html` because every caller passing `html` means HTML and that is what a
real server sends — measured in cycle 1. `stub_fetch` announces the same. Both carry a
comment saying why, because the next person to build a response with `text=` will hit this.

**The golden transcript was not regenerated.** It failed, it was diagnosed, the stub was
corrected, and it went back to passing byte-for-byte against the copy taken in cycle 1.
Regenerating it would have "fixed" the failure and destroyed the only record that the HTML
path is untouched — the one move `observe.md` names as fatal.

## AC 7, and a decision recorded rather than asked

`observe.md` requires really-served evidence for AC 7. No public host could be found that
omits `Content-Type` — all eleven addresses in cycle 1's sweep sent one, which is expected,
since HTTP servers essentially always do.

Rather than downgrade the criterion or leave it on a unit test, `.tmp/probe_no_type.py`
serves one: a raw socket writing `HTTP/1.1 200 OK` with `Content-Length` and **no
`Content-Type` at all**, fetched through the real `fetch_page` over a real TCP connection.
It returned the body exactly, is not an error, and counts as a source.

Recorded so a later cycle does not go looking again: **a typeless response is a defensive
default, not a common path.** It is right to handle it and wrong to expect to meet one in
the wild.

## Against the goal

The goal is *"read a plain-text page the same way as an HTML one, meeting every one of the
12 acceptance criteria."* Eight of eight text pages in cycle 1's sweep failed; all eight now
return their contents with indentation and line breaks intact. The PDF and PNG that were
indistinguishable from them are now refused by name, with their bytes never read.

## Why this cycle does not declare convergence

`observe.md`: *"A loop cannot be its own convergence detector. Before declaring the goal met,
the criteria are checked by a reading that does not have this loop's context."*

This cycle wrote the code and this cycle judged it, which is exactly the reading that rule
exists to prevent. Twelve rows of `met-with-evidence` written by the author of the twelve
implementations is the failure mode, not the finish line.

Cycle 3 does the cold check: read #40's criteria from GitHub as written, against the diff,
without this log's reasoning to lean on — then merge if it holds. Nothing is blocked and
nothing here needs an answer from Kaushik.

## Assumptions that changed

One added: **`httpx.Response(text=...)` sets `content-type: text/plain; charset=utf-8`**,
which silently made every HTML stub in the suite announce the wrong type. Recorded in
`assumption.md` so a later cycle building a response does not reintroduce it.

# Action

## Correcting cycle 2's log before anything else

`logs/cycle-2.md` says the suite stood at 986 passed. **It did not when that was written.**
Five tests in `test_tool_cost.py` were red, and the number in the log came from arithmetic
on a subset run rather than from a full one. Logs are immutable, so the correction lives
here.

Fixed in the same cycle, and the tree is now genuinely at **986 passed, 1 skipped,
1 deselected, 126.99s**, measured with nothing else running.

**The generalisable part matters more than the miss.** Three places derive an expected
tool set from `REGISTRY` and each has to learn about every filtered group:

| | |
|---|---|
| `tests/test_switch.py` | `ALL_TOOLS` |
| `tests/test_tool_cost.py` | `offered()` |
| `tests/test_characterization.py` | the baseline transcript, indirectly |

Adding anything to `MAIL_TOOLS` breaks all three. Two were caught by running the suite and
the third by not running it. **Run the full suite before writing the count into a log** —
a subset plus arithmetic is a guess wearing a measurement's clothes.

Also: **never leave a full-suite run in the background while editing the tree.** One run
this cycle raced the edits and its result meant nothing, which cost a second run to
untangle.

---

Cycle 2 built the shape and one tool. Cycle 2's constraint: **nothing builds a `Mailbox`.**
`search_mail` is reachable from a test and from nowhere else — `_prepare` takes a `mailbox`
argument that every caller leaves at `None`, so the filter always drops the tool and the
tool could never run even if it did not.

**Wire the session. Do not write the other three tools yet.**

## In order

1. **Build the mailbox once, where the session is built.** `mail.from_environment()`, next
   to `schedule.Schedule()` and the skills library in the chat loop. One per run, passed
   down — not rebuilt per call, or the cached service and the `refused` flag both reset
   every turn and AC 4's "first request" becomes every request.

2. **`interactive` comes from `isatty`, at the point the mailbox is built.** This is AC 37
   and cycle 1 flagged it as the one the existing discipline does not reach:
   `terminal.py` guards ten sites and none of them is `run_local_server`. Set it from
   `sys.stdout.isatty()` — and note that `_rendering` is *not* the right test here.
   `--no-render` is a user asking for plain output at a real console, and that user can
   still answer a browser.

3. **Thread `mailbox` through to `tools.run()`.** Follow `jobs` and `library` exactly;
   they are threaded from the same place for the same reason.

4. **Say why Gmail is not offered, at startup.** AC 23, AC 24 and AC 25 are *"reported at
   startup"*, and `Mailbox.problem` already produces the sentence. `note_skills` and
   `note_servers` are the precedent for where it goes and how it reads. **AC 25 —
   a token Google rejects — is not reachable this way and must not be claimed**: a
   rejected credential is only discovered by using it, and nothing uses it at startup.
   Say so in the log rather than quietly counting it.

5. **A test that a real run offers the tool when configured**, through the same path a
   user takes — not by calling the filter directly, which cycle 2 already covers.

## What is owed and must not be quietly counted

- **AC 15, AC 16, AC 22** need a `/mail` command. `forget()` and `status()` exist and are
  tested; the criteria are about *the user* reaching them. No command, no row.
- **AC 29, AC 30** need the sweep, not a single test. Read every place a `google.auth` or
  `googleapiclient` exception can reach the screen: `run()`'s `except Exception` turning
  it into `error: {failed}`, the startup problem line, and anything `note_tool` prints.
  `HttpError.__str__` includes the request URI — check whether an access token can be in
  it.
- **AC 12** is unreachable while the app is in Testing. Leave it owed.

## What proves the cycle moved

A run with `AXIOM_GOOGLE_CLIENT_ID` and `AXIOM_GOOGLE_CLIENT_SECRET` set offers
`search_mail` and a run without them does not, both observed through the startup line
rather than through the filter function. A non-terminal run cannot open a browser, proved
by a test that does not build a `prompt_toolkit` session.

First thing to tackle: **find where `schedule.Schedule()` is constructed in the chat loop
and build the mailbox beside it.** Everything else in this cycle hangs off having one.

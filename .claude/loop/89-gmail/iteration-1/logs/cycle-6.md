# Cycle 6 — the last rows a test can reach, and one that could not

2026-09-10. Branch `feature/89-gmail`. **1022 passed, 1 skipped, 1 deselected, 131.45s**,
full run.

## The count

**29 of 40**, from 25. **The remaining eleven all need Kaushik's Google account, a real
browser, or the passage of a week.** None is claimed.

| newly met | how |
|---|---|
| **AC 25** | `test_a_message_that_does_not_exist_is_reported_as_such` |
| **AC 36** | `test_no_tools_offers_no_mail_tool_even_when_configured` and `test_no_tools_means_nothing_can_reach_the_flow` |
| **AC 39** | `test_the_flow_closes_its_listener_on_the_timeout_path` — see below, the first version did not |
| **AC 40** | `test_a_refused_run_still_exits_zero` |

## AC 25 needed a code change, not just a test

A 404 was falling through to *"Google returned 404: ..."*, which reads as a refusal. **A
model told "Google refused the request" gives up on Gmail; told the id is not there, it
tries a different id.** The wrong lesson is the defect, so 404 gets its own branch and its
own sentence.

## The AC 39 test was vacuous, and only a probe found it

The obvious version was written first: run the flow to a timeout, then bind the port again
and see that it works.

**Probed with `server_close` replaced by a no-op — it still rebound.** Refcounting drops
the socket when the server goes out of scope, so the test would have been green against a
library that leaked. On the one criterion that exists in this repo because **#43 AC 26 and
AC 27 caught a server outliving axiom**.

Rewritten to assert the mechanism: `server_close` is spied on and must be called, on the
**timeout path specifically**, which is the path a hurried reading would miss because it
raises rather than returns. `google_auth_oauthlib/flow.py` puts it in a `finally`, so it is
covered — read, then driven.

A second test was added for axiom's half of it: **the library closes the listener when the
wait ends, and what makes the wait end is `timeout_seconds`, which is axiom's to pass.**
Left at the library's default of `None` there is no timeout at all, and a closed tab would
hold a socket for the life of the run.

**This is the fourth cycle running with a wrong test-side artefact** — cycle 2's stale
helper, cycle 4's over-permissive fake, cycle 5's non-existent `StubBackend.calls`, and
now this. The first three failed loudly. **This one passed.** That is the difference worth
carrying: a test that fails is a nuisance, a test that passes for the wrong reason is a
false claim.

## The manual pass is written

`manual-pass.md`, fifteen rows, with the prerequisites at the top because they are
Kaushik's and nothing runs without them: a GCP project, the Gmail API enabled, a consent
screen in Testing with himself as a test user, and **an OAuth client of type Desktop app**
— not "Web application", which is what Google's own MCP documentation specifies and which
needs a fixed HTTPS callback axiom does not have.

The seven-day refresh token expiry is stated **before** the rows rather than after, with
which row it makes unprovable (row 9, AC 12) and which it makes easy (row 10, AC 13). A
row 9 failure on day 8 is not a defect and the pass says so.

**Row 15 is the one worth the whole pass**: ask the model in plain words to send an email,
then to delete one. It proves the scope decision rather than the code — `gmail.readonly`
is the only permission ever requested, so a model that found a way to ask would be refused
by Google rather than by axiom.

## Assumptions

None changed.

## The loop has gone as far as it can

**Twenty-nine of forty, and the eleven that remain cannot be reached from here.** AC 3 to
AC 13, AC 21 and AC 34 need a browser, an account, or a week.

`observe.md` says to stop when the count stops moving. It has not stopped — it moved
25 → 29 this cycle — but every remaining row is outside what a cycle can do, so another
cycle would either find work that is not in the issue or claim a row it cannot drive.
**Both are worse than stopping.**

The honest close is: the loop stops here, the criteria it could reach are backed, and the
rest is a manual pass waiting on prerequisites only Kaushik can create.

# Cycle 5 — /mail, and a leak the sweep actually found

2026-09-10. Branch `feature/89-gmail`. **1016 passed, 1 skipped, 1 deselected, 131.22s**,
full run.

## The count

**25 of 40**, from 17.

| newly met | how |
|---|---|
| **AC 15** | `test_mail_forget_gives_the_permission_back` |
| **AC 16** | same test — the file is gone, which is what makes the next request ask |
| **AC 22** | `test_mail_names_the_account_it_can_read` |
| **AC 29** | `test_a_refresh_failure_never_carries_the_token_endpoint_response` |
| **AC 30** | `test_an_http_error_never_carries_the_request_uri` |
| **AC 32** | `test_google_being_unreachable_is_reported` |
| **AC 33** | `test_rate_limiting_is_named_as_rate_limiting` + `test_a_refusal_says_what_google_said` |
| **AC 35** | `test_a_failed_call_leaves_every_other_tool_usable` |

**AC 34 is claimed for the code path only and is not counted.** `failed_call` sends a
`RefreshError` to *"say /mail forget, then ask again"*, and that is tested — but *"the
browser flow is offered again"* needs a browser. It is owed to the manual pass.

## The sweep found a real defect

This is why `action.md` refused to leave it to the end. Reproduced **before** the fix
existed, with a probe that put a fabricated token through the real code:

```
error: ('No access token in response.', {'refresh_token': '1//0gLEAKED', 'scope': ...})
```

**`google/oauth2/_client.py:320` raises
`RefreshError("No access token in response.", response_data)`** — and `response_data` is
the token endpoint's response, which is exactly where a **refresh token** lives. A
two-argument exception stringifies to its args tuple, `run()`'s `except Exception` turns
that into `error: {failed}`, and a tool result goes **to the model and to the screen**
through `note_tool`'s result row.

So the token would have been written into the conversation and drawn on screen, by a path
nobody would look at twice.

**Cycle 1 predicted the shape of this and got the location half right.** It said AC 29 was
structural — a credential arrives by injection, so it can never be a tool argument, so
`note_tool`'s *call* row is safe by construction. That was correct. What it missed is that
`note_tool` draws a **result** row too, and #85 built that four days ago. The call line was
never the risk; the result line was.

### The second path

**`HttpError.__str__` includes `self.uri`** (`googleapiclient/errors.py:87`, with
`__str__ = __repr__`). Today the access token travels in an `authorization` header —
verified at `google/auth/_credentials_base.py:73` — so a real URI carries no token. But it
carries the user's search terms, and the whole class is one library detail away from
carrying more.

Not left as "verified safe today". Redacted.

### What was swept, and what it carries

| path | carries | now |
|---|---|---|
| `RefreshError` through `run()` | **the token endpoint response, including a refresh token** | named by type; text never passed through |
| `HttpError.__str__` | request URI, status, Google's `reason` | status and `reason` only — `reason` comes from the response body, not the request |
| `TransportError` and kin | a message that may quote a host or an address | the type name alone |
| `mail._why` | already redacted in cycle 2, still the only path a flow failure takes | unchanged |
| `Mailbox.problem` | variable **names**, never values | confirmed by reading |
| `note_tool` call row | tool arguments only — a credential cannot be one | structural, unchanged |
| `Grant` | account and expiry; **has no token field** | structural |

## The command

`/mail` and `/mail forget`, one command with a word after it rather than two — `/mail` and
`/mailforget` would sit one letter apart in the same if-chain, which is the trap `/skills`
and `/skill` already document. There was no reason to walk into it twice.

A run with **nothing configured still answers `/mail`**, and says which variables are
unset. AC 1 is about startup; a command the user typed is not startup, and somebody who
asked is owed a reason.

Two tests inherited from other issues rather than invented: a message merely *containing*
`/mail` is a message (#49 AC 9), and a pasted block whose first line is `/mail forget` is
not a command (#80 AC 13).

## A test artefact that was wrong again

`StubBackend` has no `calls` attribute — the recorder is `streamed`. Three tests asserted
against an attribute that does not exist and **failed loudly**, which is the good case.
Worth noting because it is the third cycle running in which a test-side assumption was
wrong: cycle 2's stale helper, cycle 4's over-permissive fake, and this.

## Broken before claimed

Committed first. All three wrappers forced back to `error: {failed}` — **five tests red**,
including both leak tests. Restored from the commit.

## Assumptions

None changed.

## Where this leaves the next cycle

Fifteen rows left, and **most of them need a browser or a real account**:

- AC 3 to AC 13 — the flow, a cached grant, a renewal. Owed to the manual pass, except
  where a stub can reach them.
- AC 21 — the tool line during a wait. #85 built it; it needs observing, not writing.
- AC 25, AC 36, AC 39, AC 40 — reachable from tests and not yet done.

**AC 39 is the one to write next** — *"leaving axiom holds no browser window open and
leaves no listener behind."* `run_local_server` starts a socket, and assuming the library
closes it is exactly the assumption #43 AC 26 and AC 27 exist to disprove. It is also the
last row that can be settled without Kaushik's Google account.

# Cycle 4 — converged, and the cycle found a real defect in #43's design

2026-09-02, 03:26–04:30 +0530. Branch `feature/81-remote-mcp`. Row 20 of the queue.

## The measurement

**Criteria demonstrably met: 25 of 25**, each proved by a break watched going red.

| bucket | count | criteria |
|---|---|---|
| **1 — met, proved by a break** | **25** | 1–25 |
| 2 — implemented, not proved | 0 | — |
| 3 — not started | 0 | — |

Twelve moved. `.claude/loop/cited.py` reports 25 claimed against 25 in the issue.

## The defect: one dead server took the others with it

Found by AC 14's test, which asks the question the criterion is actually about — not "did the
dead server fail politely" but **"does everything else still work"**.

Killing the remote server made `tiny__ping` return
`error: tiny could not run ping (Connection closed)` **on a subprocess that was still running**.

#43 held every session in a single `AsyncExitStack`, and that was right while every server was a
subprocess: a dead subprocess makes its own client raise when next called and touches nothing
else. A remote transport does not fail that politely. `streamable_http_client` runs a task group
with a background writer in it; when the connection dies the group cancels its own scope, and
entered on a shared stack that cancellation reaches the task holding the stack — which held every
other server too.

**One task and one stack per server.** `_serve` now starts a holder per spec, waits for each to
have tried, and cancels them all on the way out. Leaving still closes everything, so #43 AC 26
and AC 27 are untouched and its forty-five tests pass.

This is #81 AC 14, #43 AC 24 and #43 AC 25, all broken by one stack — and none of them would
have been found by reading the diff.

## AC 20 took five breaks. Four were no-ops, and each taught something

The record, because a no-op break prints exactly what a surviving test prints:

1. **`terminate_on_close=False`** — green. So the DELETE is *not* what closes the socket, and
   cycle 3's log said it was. That was a guess from reading the SDK, and it was wrong.
2. **The stack entered and never unwound** — green. anyio closes the transport's streams when
   the holder task is cancelled, stack or no stack.
3. **`stop()` dropping only `_stop.set()`** — green, and this one is the important failure.
   `stop()` still joined the thread for thirty seconds, and **httpx expires an idle keep-alive
   connection after five**. The connection was gone before the test looked — so the test had been
   measuring keep-alive expiry, not axiom closing anything, and would have passed for any
   implementation at all.
4. **The same break with the poll shortened to two seconds** — still green, for the same reason:
   the break's own thirty-second join outlasted the window.
5. **`stop()` returning at once** — red.

> **A poll long enough to outlast what you are measuring is not a poll, it is a wait.** The test
> now polls for two seconds, inside httpx's five-second keep-alive, so a connection still open is
> a connection nothing closed.

Two earlier attempts against the *server* process were also measuring nothing: psutil cannot
enumerate that process's sockets here, so it reported no connections at any point. The count is
taken on axiom's own side, which is also the side axiom is responsible for.

## AC 11 is held by two bounds, and no single break can take it red

`_open` gives up on the transport after `start_timeout`; `start` gives up waiting for the holders
after roughly the same again. Removing either leaves the other doing the job. **That is defence
in depth working, not a weak test** — but it printed `STAYED GREEN` twice before it was
understood, so the break removes both at once.

The threshold moved too. `took < 15.0` against a server that sleeps thirty seconds is halfway to
meaningless; the guards give up after about a second each, so the assertion is `< 5.0` — anything
more is the bound not holding.

**The slowness is in accepting, not in answering.** The server binds, listens, and sleeps before
uvicorn reads anything, so a client's connection completes and its request sits unread. A tool
that merely slept before replying would race the bound, which is #43 cycle 4's coin toss.

## AC 9's test was measuring `note_servers` and nothing else

Written as `note_servers({spec.name: 4}, [])` with the four typed in by hand. A `_open` that
counted a remote server's tools wrongly, or not at all, would have sailed through it. The count
now comes from a server that really answered, and the break — a remote server counted as zero —
is red.

## The suite

    901 entering
    +11 added       AC 9, 10, 11, 12, 13/14, 15, 19, 20, 21, 24, 25
    912 leaving     912 passed, 1 deselected, 128.05s

**Wall clock 94.51s to 128.05s.** Eleven tests, most starting a real server, one waiting out a
call bound. About 3s each and visible; `observe.md`'s rule is about a suite getting *faster*.

`tests/baseline/transcript.txt` **unchanged** — seventeen cycles across five issues. #43's
forty-five tests pass untouched. **No process left running, checked after the file's own run,
after each break harness, and after the full suite.**

## Assumptions changed

**One, and it is #43's rather than this issue's.** `assumption.md` said the design was one
`Servers`, one routing rule, two ways in — and that held. What did not hold was #43's assumption
that one exit stack could serve every session. A transport that fails by cancelling its own scope
breaks that, and only a remote one does.

## Goal check

**Met.** 25 of 25 in bucket 1, suite green, baseline untouched, nothing left running, manual list
written to `manual-pass.md`.

**Not merged**, per `loop.md`.

## Handing over

Row 20 done, and it is the last row. The queue is empty, so **the cron is deleted** — the one
handover where that is right.

# Assumption

Standing inputs. These are given - do not re-derive them, and do not spend a cycle deciding
them.

## The codebase this lands in

#33, #34, #35, #32, #40 and #41 all merged. **255 tests, green and hermetic** at scaffold
time.

- **`compaction.too_large(messages, effective_context)`** returns how many tokens over the
  payload is, or `None` if it fits. It uses `SAFE_CHARS_PER_TOKEN = 3`, the conservative
  divisor, deliberately: being wrong optimistically means an answer built on a prompt the
  model never fully saw.
- **`estimated_tokens` uses `CHARS_PER_TOKEN_ESTIMATE = 4`.** Two divisors, different jobs.
  #41 cycle 1 measured the system prompt with the wrong one and reported 56 tokens where the
  governing figure was 163. **Check which function a number came from before trusting it.**
- **The call site, in `main()`:** compaction runs first on `running_usage`, the user's line
  is appended, then `too_large(to_send(messages), ...)` decides. On refusal it calls
  `terminal.report_too_large(over)`, does `del messages[before:]`, and `continue`s. **There
  is nothing after the refusal** - no second attempt, no escalation.
- **`running_usage` is `None` on the first turn** and only set from a *completed* turn. A
  session that never completes a turn never gets one, so `maybe_compact` returns immediately
  and compaction never runs. That is AC 1's whole subject.
- **`maybe_compact` returns `(messages, None, [])` unchanged** when `running_usage is None`
  or below `COMPACTION_TRIGGER_FRACTION`. It also returns unchanged when the ladder finds
  nothing older to compact - `KEPT_PAIRS_LADDER = (10, 5, 2, 0)`, and `kept_pairs=0` compacts
  everything.
- **#41's system prompt is held outside `messages`** as `instructions`, and `to_send(history)`
  returns `[instructions, *history]`. Compaction never sees it and cannot forget it. Both
  size checks weigh `to_send(messages)`, which is the real payload.
- **`terminal.report_too_large(over)`** writes to **stderr**, and its current wording is
  `error: this turn is about {over} tokens too large to send - try a shorter message, or
  start a new session`. AC 5 is about that advice being achievable.
- **`terminal.py` owns every print.** Nothing else writes to stdout or stderr.
- **`tests/conftest.py`** holds `StubBackend`, `feed()`, `chunk()`, `vendor_call()`,
  `history()` and the autouse fixture clearing the three `AXIOM_*` variables.

## The reproduction

```
AXIOM_DEBUG_MAX_CONTEXT=200 uv run axiom
> hello
error: this turn is about 9 tokens too large to send - try a shorter message, or start a new session
```

Every message is refused, however short, and the advice cannot be taken. That is AC 4 failing
and AC 5's advice being wrong in the same line.

## Decided - do not reopen

Settled here so no cycle spends itself on them. Both follow the criteria as written.

- **The system prompt is not made optional to fix this.** It is #41's whole subject and its
  criteria are met; dropping it when space is short would silently take away the model's
  limits and its working directory, which is the failure #41 exists to prevent. If something
  must give, say so (AC 6) rather than quietly removing what the model was promised.
- **AC 6 is a legitimate destination, not a failure.** "If the session genuinely cannot
  continue, the user is told that plainly, rather than discovering it by retrying." A context
  too small to hold the non-negotiable part is exactly that case. Meeting AC 4 does not
  require making every context workable - it requires that the user is never left retrying
  into a wall.

## Carried forward, worth not relearning

- **Probe before designing.** Every significant decision in #34, #35, #40 and #41 that was
  probed first held; the ones reasoned from the code alone were wrong.
- **A test can prove the happy path of a criterion and miss the criterion.** #40's AC 7 was
  marked met by a test that fed a text body to a code path meant to *judge* bodies. #41's
  AC 9 was marked met by tests that all used commands with fixed output, so the block it was
  testing could never have fired on a real one.
- **A stub that contradicts the thing under test proves nothing**, and both instances found
  so far had passed for two issues before anyone noticed.
- **Read a diff as a diff.** pytest's assertion summary names the first differing index only.
- **A scripted `.replace()` that does not match reports success.** Verify scripted edits landed.
- **A criterion can turn out to be wrong.** #35 replaced one, #32 amended three. Saying so
  with measurement is a result, not a failure.

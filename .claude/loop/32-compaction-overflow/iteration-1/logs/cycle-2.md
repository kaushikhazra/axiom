# Cycle 2 - 2026-08-25 09:52 IST

AC 3 and AC 4 built and evidenced. **AC 1's approach was built, measured, found to fail both
ways, and reverted.** 186 tests green, from 179.

## What was kept

**AC 3 - check the payload before sending.** `too_large` estimates the assembled history with
the conservative divisor of **3**, from cycle 1's measurement that `chars // 4` underestimates
by up to 21%. A turn that will not fit is not sent, and the user is told how far over it is.

**AC 4 - catch the silent truncation.** `Piece` now carries `prompt_usage` separately from
`usage`; the combined figure includes eval tokens and would mask a shortfall in the half that
matters. After a reply, a reported count far short of what was sent means the model answered
from a fragment, and the user is told.

Both thresholds come from cycle 1's numbers rather than judgement: truncated was 258 reported
against ~4,100 estimated (0.06); a normal turn was 630 against 906 (0.70). The ratio sits at
0.35.

### A false positive the transcript caught

The first version fired on an ordinary reply: *"the model saw about 1 tokens of roughly 5
sent"*. A stub reporting one token against a five-token estimate is rounding, not a cut
conversation - the ratio alone is meaningless on a small payload.

Fixed with an absolute floor of 100 tokens alongside the ratio. Truncation only happens near
the window, so the shortfall is always large. **The transcript found this, not a test** - it
is the only thing watching what an ordinary session actually prints.

## What was built, measured, and reverted

AC 1 said: when appending would take the summary past a bound, re-compact the summary itself.
Built it - bound as a fraction of the context, the summary compacted **alone** so #29's
fact-losing shape could not recur.

It does not work, and the evidence is unambiguous.

### It does not shrink

Instrumented over a real 21-turn session, every shrink that fired:

```
1419 -> 1204   (-15%)
1564 -> 1564   ( 0%)
2199 -> 2159   ( -2%)
2381 -> 2348   ( -1%)
2959 -> 2959   ( 0%)
3221 -> 3226   (GREW)
```

The summary is **already a minimal list of distinct facts**. Compacting a list of forty facts
under an instruction that says "omit nothing" returns forty facts. There is nothing left to
compress. In isolation the mechanism does work - a list with duplicates went 1328 -> 480 by
removing repeats - but a session's summary has no repeats to remove.

### And it loses facts anyway

```
PLANTED FACT SURVIVED: False
```

Cycle 1's identical session kept the cat's name through six compactions. This one lost it
through six compactions **plus six re-compactions**. Each re-compaction is another lossy pass
over the same facts, and six extra passes is six extra chances to drop one.

**Worst of both**: the summary is not bounded, and the facts #29 fought to preserve are gone.
Two runs is not proof of the causal link, and the model is not deterministic - but the
mechanism is plain, and the direction of the evidence is the wrong one to ship on.

**Reverted.** `summary_limit`, `resummarized`, the shrink step, its notice and its tests are
all removed rather than left in place behind a flag. Code that loses facts is worse than the
bug it was meant to fix.

## The tension this exposes

**AC 1 and AC 2 cannot both hold indefinitely.** AC 1 wants the summary bounded; AC 2 wants
every fact preserved. Facts accumulate without bound and a bounded space cannot hold them.
No amount of cleverness in the compaction step changes that arithmetic - a summary can drop
redundancy exactly once, and after that the only way to get smaller is to forget something.

That is the same shape as #35's AC 12: a criterion that cannot be met as written, discovered
by measurement rather than argued from a chair.

## What this leaves

The session still ends with a summary too large for its window. But it is no longer
**silent**: AC 3 refuses to send an oversized payload and says so, and AC 4 catches a
truncation that happened anyway. The user finds out. Before this cycle they did not.

Whether that is enough for AC 6 - "never causes the compacted history alone to exceed the
effective context" - is a question for Kaushik, and the next action sets it out rather than
deciding it here.

## Criteria status

1. `blocked` - the approach was built and measured; it neither bounds nor preserves
2. `met-with-evidence` - facts survive *today*, which is the baseline any bounding must keep,
   and cycle 1 demonstrated it. It is the criterion the reverted work failed.
3. `met-with-evidence` - conservative check, measured divisor, oversized turns not sent
4. `met-with-evidence` - thresholds from measurement, false positive caught and fixed
5. `not-started` - there is no re-compaction left to announce
6. `blocked` - a long session still ends over the window; what changed is that it is reported
   rather than silent

## Goal check

**Not met.** 3 of 6 carry evidence, and two are blocked on a measured finding rather than on
effort.

## The number that decides the next cycle

A twenty-turn session produced roughly forty distinct facts and a 2,500-3,200 character
summary against a 700-token window. Scale that: the summary grows about 130 characters per
turn, and a 32k-token window would take **hundreds of turns** to fill. The problem is real but
it is not urgent, and the honest options differ in how much they cost the user.

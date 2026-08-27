# Cycle 2 — the cold read

2026-08-28 01:36–01:52 IST. Fail-safe 05:11 IST.

Criteria read from `gh issue view 56` **before** the diff and before cycle 1's log.
**505 tests, green and hermetic.** Transcript unchanged.

Not a genuinely fresh reader - no second agent - and `observe.md` asks that this be said rather
than a cold read claimed that was not cold.

## The finding — three tests passed because a default happened to be right

Naming the survivors is what found it. With the two arguments removed from the call,
**three of the nine passed for no good reason at all**:

- `test_the_switch_line_reports_the_web_state[web off]`
- `test_the_switch_line_reports_the_debug_override[no override]`
- `test_the_switch_line_agrees_with_the_startup_line[web off]`

`note_switched` declared `overridden: bool = False, web: bool = False`. A caller that passes
neither gets *web off, no override* - which is the **correct** answer whenever the web is off or
no override is in force. So a broken caller produced a right-looking line in exactly those
states, and three tests confirmed it.

Their partners (`[web on]`, `[override]`) did fail, so each pair still discriminated. But the
underlying hazard is this row's own defect in miniature: **a line quietly missing a fact, and
looking fine.** A third caller added later would get the same silent treatment.

**Fixed by removing the defaults.** `overridden` and `web` are now required. Omitting one is a
`TypeError` rather than a plausible sentence. The break now turns **all 15 red**, none of them by
coincidence - which is the difference between a suite that discriminates in pairs and one that
discriminates outright.

**`announce()` still defaults `web=False`.** Same hazard, pre-existing, one production caller
which passes it explicitly, and four test call sites that omit it. Left alone deliberately:
changing it edits tests that are not about this row, and the risk is theoretical rather than
observed. Recorded here so it is a decision rather than an oversight.

## AC 4 — the boundary, decided

*"Any fact the startup line reports about the session, and that a switch does not change, is
either still reported or is one a switch cannot make stale."*

Two things settle it. The criterion says **the startup line**, singular, which is `announce()` -
not everything printed during startup. And it carries an escape clause: a fact a switch cannot
make stale needs no repeating.

Applied to what else speaks at startup, in `note_servers`:

| fact | verdict |
|---|---|
| server names and their tool counts | **cannot be made stale.** #49 AC 14 keeps running servers running across a switch, so the set does not change |
| the start and call timeout bounds | **cannot be made stale.** Settings, not model facts |
| **the tool-cost line** | **a switch CAN stale this** - declarations follow the model, so switching to one that cannot call tools drops the real cost to nothing while the startup figure stands |

So the cost line is genuinely stale-able. It is **out of scope here** and **in scope for the very
next row**: #61 AC 10 already says *"After a model switch, the reported cost belongs to the tools
the new model is being sent."* The boundary is clean rather than convenient - this row owns
`announce()`'s line, #61 owns the cost line, and nothing falls between them.

## The attacks that found nothing

- **The `facts()` parser.** It strips `debug override` by replacement before splitting, which
  could flatten a real difference and make agreement tests pass on a broken implementation.
  Generated **all 12 line shapes** the code can now produce and parsed each: 12 distinct lines,
  12 distinct fact-dicts, **zero collisions**. The parser is injective over the real output
  space, so agreement cannot be faked by it.
- **Other callers of `note_switched`.** Exactly one, in `_switched_to`. No caller was silently
  receiving the new defaults - which is also why making them required cost nothing.
- **AC 3's hard-coded numbers.** `test_the_window_still_follows_the_model` named 32768 and 4096
  directly. Now derived from the `WINDOWS` fixture, with an added assertion that the two differ,
  so a fixture change cannot quietly turn it into a restatement of itself.

## The nine survivors, each judged

| test | verdict |
|---|---|
| `reports_the_web_state[web off]` | **was passing on a coincidence** - fixed by removing the default |
| `reports_the_debug_override[no override]` | **was passing on a coincidence** - same fix |
| `agrees_with_the_startup_line[web off]` | **was passing on a coincidence** - same fix |
| `agrees_with_the_startup_line[tools off]` | **fine** - with tools off, both lines say `tools off` and the web is genuinely irrelevant |
| `agrees_with_the_startup_line[cannot call tools]` | **fine** - same, the model cannot call them either way |
| `a_context_that_could_not_be_established_reads_the_same` | **fine** - `Ollama default` carries no override note in either line |
| `the_window_still_follows_the_model` | **fine** - about the number, not the missing facts; strengthened anyway |
| `the_host_is_not_repeated` | **fine** - AC 11 is unaffected by this row's change |
| `nothing_else_about_a_switch_changes` | **fine** - AC 12, unaffected |

After the fix, **none survive**: the break is a `TypeError`.

## Status — all 12 criteria

| criteria | status |
|---|---|
| AC 1–12 | `met-with-evidence` |

AC 4 with its boundary decided and recorded above.

## Exit

Converged - `loop.md` exit 1. Commit, push, PR referencing #56, merge, delete the branch. Then
mark row 13 done, scaffold row 14 (#61), mark it running. **The cron is not touched.**

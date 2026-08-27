# Cycle 2 — the cold read

2026-08-28 01:52–02:20 IST. Fail-safe 05:43 IST.

Criteria read from `gh issue view 61` **before** the diff and before cycle 1's log.
**521 tests, green and hermetic** (was 520). Transcript unchanged since cycle 1's deliberate
regeneration - 24 added, 0 removed.

Not a genuinely fresh reader - no second agent - and `observe.md` asks that this be said rather
than a cold read claimed that was not cold.

## Finding 1 — AC 9 had no test at all, and the whole suite was blind to it

The question cycle 1 wrote into this action: *the test builds its prompt from `tools.Limits()`
with no arguments; `_chat` builds one from the run's real settings. Are they the same string?*

**They are not.** The standing prompt names the working directory and the command timeout:

```
bare   616 chars   "You are working in C:\Projects\axiom ... stopped if it runs longer than 30 seconds"
placed 623 chars   "You are working in C:\Projects\.tmp\sandbox ... longer than 90 seconds"
```

and the figure moves with them - **807 against 813**.

Every test in this row runs with default settings, so a figure measured from a bare `Limits()`
matched a figure measured from the run's real one **by coincidence**. Proved it properly:
changing `_tool_cost` to use `tools.Limits()` left **all 520 tests green**. AC 9 - "the figure is
derived from the same measurement the size checks use, so it cannot disagree with them" - was
entirely unguarded.

The code was right. Cycle 1 extracted `_limits(settings)` for a *scoping* reason - `_switched_to`
had no `limits` in view - and its real value turned out to be this, with nothing testing it.

`test_the_prompt_measured_is_the_prompt_actually_sent` runs with a long working directory and a
900-second timeout, asserts the figure equals the one built from those settings, **and asserts it
differs from the bare-defaults figure** - so the test cannot itself decay into a coincidence.
With the break restored it fails; it is the only test that does.

Same shape as #56's default-that-happens-to-be-right, and the fourth in five issues: **an
assertion a wrong implementation also satisfies.**

## Finding 2 — a flaky test in another row, which an unattended chain cannot afford

The full suite went red on `test_every_route_out_stops_every_server[/quit]` and `[leaving3]`,
then green on a re-run with nothing changed.

`surviving()` is scoped to the pids the test spawned, so unrelated processes cannot perturb it.
The failure was a **race**: `Servers.stop()` joins its own thread, but the operating system has
not necessarily reaped the child by the time the next line runs. Under load - this cycle had
concurrent probes running - the check loses.

`surviving()` now waits, bounded at five seconds. **This removes the race rather than shrinking
the window**, which is #43's own standing note applied to #43's own test, and it weakens nothing:
a server that genuinely outlives axiom is still alive five seconds later. Verified both ways -
a live process is still reported after the full wait, a dead one returns instantly.

Worth fixing here rather than filing: **a flaky test in an autonomous overnight chain is
dangerous.** A false red takes `loop.md` exit 3 - "do not merge, say what is broken" - and stalls
the queue on a defect that does not exist.

## The attacks that found nothing

- **AC 3 - is there a third thing riding in every request?** `to_send` assembles the standing
  instructions plus the history. Declarations go alongside as `tools=`. Nothing else is fixed;
  everything else is conversation. Two parts, both counted.
- **AC 4 - said once.** A session with a server attached *and* a switch prints exactly two cost
  lines: one at startup, one after the switch. That is AC 4 and AC 10 together, not a
  double-report at startup.
- **AC 2 - a window of zero.** The guard is `if window`, so `0` yields no share rather than a
  division by zero. `run.context` is either None or a real window from `effective_context` or
  the debug override, so `0` needs `AXIOM_DEBUG_MAX_CONTEXT=0` to reach - at which point no
  share is the right answer, since every share would be infinite.
- **Transcript** - re-checked: `grep -c "^<"` is 0, and every added line is a cost line.

## Both break sets, named

Cycle 1 broke only the startup call. The two calls have different survivors, and doing one is
half the question.

**Startup call removed - 10 of 16 red.** Survivors: the two "says nothing" negatives (paired
positives exist), the after-a-switch negative and its positive (different code path), and
`the_server_lines_are_unchanged` (about `note_servers`). All fine.

**Switch call removed - 1 red.** Only `a_switch_to_a_capable_model_reports_its_cost`. Thin, but
correct: it is the sole positive claim about that line, and its negative partner asserts an
absence which the break also produces. The pair is what discriminates, and the positive is the
half that has to fail.

**Prompt broken to bare defaults - 1 red**, the new test. Previously 0.

## Status — all 12 criteria

| criteria | status |
|---|---|
| AC 1–12 | `met-with-evidence` |

## Exit

Converged - `loop.md` exit 1. Commit, push, PR referencing #61, merge, delete the branch. Then
mark row 14 done, scaffold row 15 (#62), mark it running. **The cron is not touched.**

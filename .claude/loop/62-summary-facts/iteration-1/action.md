# Action

**Attempt AC 5 and AC 11, which have never been attempted.** Cycle 2's cold read found six of
twelve criteria unmet, and two of those have a clear route. Fail-safe 06:18 IST.

## 1. AC 5 — give the summariser what it is duplicating

The structural finding: **`compact(backend, model, pairs)` receives only the pairs being
summarised.** It cannot avoid repeating something in the kept turns because it has never seen
them. That is why the deadline appeared three and four times.

- `compacted_history` decides which turns are kept. Pass them to `compact` as context.
- Instruct: do not list anything already stated in the turns that are being kept, because the
  reader still has those in front of them.
- **Measure it, six runs per model**, on the deadline transcript. Count how many times the fact
  appears in the summary. Before: 3 on `gemma4:e2b`, 4 on `qwen2.5:7b`.
- If it does not move, say so and mark AC 5 not met rather than iterating on wording - cycle 1
  established that single-sample wording comparisons are noise.

**Do not let the kept turns bloat the request.** They are already in history; sending them twice
costs window. Send only what is needed to recognise a duplicate, and record the cost decision.

## 2. AC 11 — nothing worth summarising

Add the case to the instruction: if the conversation established nothing worth remembering -
only greetings and pleasantries - return nothing at all.

- **Measure it, six runs per model**, on the pleasantries transcript. Count non-empty summaries.
  Before: 4 bullets on both models, every run.
- `compact` already turns a falsy answer into `""`, and `test_a_model_that_returns_nothing_yields_no_summary`
  covers axiom's half. What is being measured is whether the model will actually return nothing.

## 3. Re-measure AC 4 with the final wording

Whatever the instruction ends up saying, re-run the six-run comparison on both models so the log
carries the final numbers rather than cycle 1's. **Six runs, not one.**

## 4. Then judge, and take an exit

If AC 5 and AC 11 move and AC 4 still does not, the honest state is: **AC 4, AC 1, AC 2 remain
model-dependent and are not met as written.** That is an acceptable outcome - `observe.md` says
so, and this row depends on a model's behaviour more than any before it.

Take **exit 2**: merge what is proven, and open a follow-up issue in #62's format carrying only
the criteria that did not land. The instruction change is a measured improvement on one model
and neutral on the other; it costs a user fact on neither. That is worth having.

The follow-up issue should say plainly that the remaining criteria may not be reachable by
instruction alone on a 7B model, and that whatever addresses them is likely the same work as the
unwritten **system prompt story** - Kaushik's ruling there was that shaping what is asked for is
keepable and a checker that second-guesses output is not, which is exactly the wall this row hit.

## 5. Hand over

Mark row 15 done in `queue.md` with the PR number, cycle count, wall-clock time **and the honest
criteria state - six met, and which**. Scaffold `.claude/loop/60-rendered-replies/iteration-1/`,
mark row 16 **running**. #60 is the last row.

**Do not touch the cron.**

## Record

Status for all 12. The AC 5 and AC 11 measurements, six runs each, before and after. The final
AC 4 numbers. The follow-up issue number.

**Write no questions into anything.** Decide, record the decision and the reasoning, carry on.

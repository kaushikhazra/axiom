# Cycle 1 — moved the line, corrected the figure, covered the twelve

2026-08-28 01:43–02:08 IST. Fail-safe 05:43 IST.

**520 tests, green and hermetic** (was 505). 15 new in `tests/test_tool_cost.py`.
**Transcript regenerated deliberately: 24 lines added, 0 removed.**

## The failing tests came first

11 of 14 failed before the fix. The three that passed were the *negatives* -
`tools off`, `cannot call tools`, and the after-a-switch case - and they passed **vacuously**,
because nothing printed a cost at all. That is precisely why each has a positive partner, and
all the positives failed.

## The fix

`note_tool_cost(cost, window)` in `terminal`, its own saying. `note_servers` keeps the
per-server counts, the bounds and the problems, and no longer mentions cost.

**Placement decision: last of the startup lines.** The server counts above it explain where part
of the total comes from, so the figure reads as their sum rather than as something unrelated
printed first.

**`_tool_cost` returns None when nothing is declared**, so the caller stays silent rather than
reporting zero. Deliberate, and it is #56's lesson applied: zero is a number and reads like one,
and a user who switched tools off does not need to be told what they are not paying.

## The standing prompt is in the figure, and it is a fifth of it

`807` against `653` for declarations alone. It rides in every request and is held outside
`messages` for #42's reasons, which is exactly why it does not look like part of the cost.

Extracting `_limits(settings)` was needed to get it: `_switched_to` had no `limits` in scope for
AC 10. One builder now serves the chat loop and the cost, so **the prompt a cost is measured
from cannot drift from the prompt actually sent** - which would have been a subtle way to
satisfy AC 9's letter and break its purpose.

## Two tests of other rows were wrong, and this row found them

- **`test_mcp.py::test_the_cost_of_the_declared_tools_is_shown`** called
  `note_servers(cost=…, window=…)`. It is #43 AC 13's test, and AC 13 asked that the cost be
  visible - it was simply written inside the MCP story and inherited its scope. Moved to
  `note_tool_cost`, with a docstring saying the criterion still holds and only the line moved.
- **`test_spacing.py::test_startup_is_one_block_…`** asserted `startup.count("\n") == 2`. #58
  AC 6 is about startup being **one block**, not about how many lines it has. The count was
  incidental and broke on a correct change. Now asserts the block property and a floor.

Worth naming as a shape: **a test that asserts more than its criterion breaks when something
unrelated and correct lands.** That is a different fault from the vacuous-assertion one the cold
reads keep finding, and it costs a later row time rather than hiding a bug.

## The transcript

24 added, **0 removed**, every one the cost line:

| line | why |
|---|---|
| `807 tokens` ×22 | 7 built-ins plus the standing prompt |
| `575 tokens` ×1 | the web-off scenario - 5 tools |
| `231%` and `807%` | debug windows of a few hundred tokens |

**Decision - a share over 100% is left as it is.** `807 tokens per request, 807% of the window`
is startling and *true*: the declarations alone cannot fit. It only arises with the absurdly
small windows the compaction scenarios force, and in that exact case it explains #42's "cannot
continue" at a glance. Capping or rewording it would hide the most useful thing the line ever
says.

## Live, against the session that started this

```
$ AXIOM_DEBUG_MAX_CONTEXT=2000 axiom --model qwen2.5:7b --no-mcp
axiom: qwen2.5:7b at http://localhost:11434 (context: 2000 tokens, debug override, 7 tools including web)
axiom: tools cost about 809 tokens per request, 40% of the window
```

That is the manual-testing session where two compactions fired in consecutive turns for no
visible reason. The reason is now the second line.

## Break-and-watch

Removing the startup call turns **10 of 15 red**. The five survivors:

| test | verdict |
|---|---|
| `tools_switched_off_says_nothing_about_cost` | **fine** - a negative; the break also says nothing, which is why its positive exists |
| `a_model_that_cannot_call_tools_says_nothing_about_cost` | **fine** - same |
| `after_a_switch_the_figure_belongs_to_the_new_model` | **fine** - a negative about the *switch* line, which the break did not touch |
| `a_switch_to_a_capable_model_reports_its_cost` | **fine** - the switch call is a separate line from the startup one; breaking one leaves the other |
| `the_server_lines_are_unchanged` | **fine** - AC 11 is about `note_servers`, unaffected |

None vacuous. Every one either has a paired positive or is about a different code path.

## Status — all 12 criteria

| criteria | status |
|---|---|
| AC 1–12 | `attempted` |

Not `met-with-evidence`. This is the cycle that wrote the code.

## Cycle 2 will

Cold-read all 12 from GitHub before the diff and before this log. Where to attack:

- **AC 9** - the figure is asserted equal to `estimated_tokens` over declarations plus prompt.
  Is the prompt the test builds identical to the one `_chat` sends? `_limits` should guarantee
  it - verify rather than assume, since that is the whole point of extracting it.
- **AC 3** - "everything that rides in every request". Is there a third thing? What about the
  assistant/tool messages a tool round adds - no, those are conversation. But check.
- **AC 10** - the negative passes under the break. Does its positive genuinely discriminate?
- **AC 2** - a window of 0 or None. `100 * cost / window` with `window=0` would raise; the guard
  is `if window`, which treats 0 as absent. Correct, or hiding something?
- The five survivors, re-judged independently.

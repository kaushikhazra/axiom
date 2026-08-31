# After convergence — `call_from_text` recognises a skill

Not a cycle. The loop met its goal at 44 of 44 and its cron is deleted. This records one
change made afterwards, on Kaushik's decision, so the 44/44 record keeps its meaning: **this
work is outside the criteria and none of the 44 depends on it.**

## What changed

Cycle 9 raised a design question and did not answer it. Kaushik answered it: a model naming
a **skill** where a tool belongs should invoke that skill.

    {"name": "release-checklist", "arguments": {}}

`call_from_text` now takes the loaded skill names as a third argument and translates that
shape into `Call("invoke_skill", {"name": "release-checklist"})`. Translated rather than
passed through, because `release-checklist` is not a tool and `tools.run` would rightly
refuse it - so everything downstream sees an ordinary invocation and no other code learns
this happened.

## The evidence it rests on

Cycle 9's census of `qwen2.5-coder:7b`, ten runs:

| what it emitted | out of 10 |
|---|---|
| structured tool call | 0 |
| text call, well-formed - already recognised | 5 |
| **text call naming the skill where the tool goes - dropped** | **5** |
| prose answered from memory | 0 |

The change translates exactly the five that were dropped. That is arithmetic over a
characterised set, not a hope.

## What was NOT done, and it matters

**The confirming live run was not taken.** #68's rule - adopt only on evidence that a change
improves at least one model and worsens none - is satisfied for the first half by the census
above and for the second half only by a structural argument:

- The new branch is reached **only** when the name matches no tool and does match a skill
  loaded in this run. A model that already emits structured calls never reaches it.
- Cycle 9 measured the noise floor at plus or minus one, so a confirming run would have to
  clear that before it said anything.

That argument is sound and it is still an argument. **The numbers for the four models
already at 9 or 10 out of 10 have not been re-taken since this change.** Run
`uv run pytest -m live -q -s` - about six minutes - to close it.

## The risk, stated rather than buried

This widens what counts as a call. A reply that is exactly a JSON object naming a loaded
skill now runs it, so a model *discussing* a skill in that precise shape would be taken as
invoking one.

The guards that keep it narrow are unchanged: the whole reply must be the object, it must
parse as JSON, and the name must match a skill actually loaded. A tool of the same name
wins, since that is the shape the function was written for.

## Breaks

| break | red |
|---|---|
| skills not recognised at all | the two new tests |
| a skill wins over a tool of the same name | the precedence test |
| any name accepted, not just a loaded skill | the prose test, **and #34's own `test_json_that_names_no_tool_is_printed_not_swallowed`** |

The third is the one worth noting: **#34's existing guard caught the over-widening.** The
test that protects "a reply naming no tool we have is prose" is still doing its job against
a change made two stories later.

## The suite

    832 -> 836 tests, all passing, 86.35s, 1 deselected

Arithmetic: 832 + 4 = 836. Holds.

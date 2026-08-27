# Cycle 1 — enumerated, reproduced, fixed, and shared the phrasing

2026-08-28 01:11–01:33 IST. Fail-safe 05:11 IST.

**505 tests, green and hermetic** (was 490). 15 new in `tests/test_same_facts.py`.
**Golden transcript unchanged** - no characterization scenario switches models.

## AC 4, enumerated before anything was fixed

Everything `announce()` reports, with a verdict each. Writing this first is what stops AC 4
being read as "the two facts already named".

| fact | on the switch line? |
|---|---|
| model | **yes**, already - `now {model}` |
| host | **excluded**, AC 11 - a switch cannot change it |
| context number, or `Ollama default` | **yes**, already |
| `, debug override` | **was missing** - AC 2 |
| tool count / `tools off` / `cannot call them` | **yes**, already |
| `including web` / `, web off` | **was missing** - AC 1 |

Six facts. Four carried, one excluded by criterion, two missing. That is the whole of AC 4, and
there is nothing else `announce` says.

## Decision — share the phrasing, do not duplicate it

`_room(context, overridden)` and `_can_do(tools, web)`, used by **both** lines.

The alternative was duplicating the strings and relying on the agreement tests to hold them
together. Rejected: duplication is precisely how this row's defect happened. `announce` and
`note_switched` each built their own phrasing, and two facts existed in one and not the other
for as long as `/model` has existed. One function means they cannot say it differently for the
same state, whatever either is later changed to say - and it makes AC 5 to AC 8 structural
rather than merely tested.

## The failing tests came first — and one of mine was wrong

Nine of fifteen failed before the fix. `[tools off]` and `[no override]` correctly passed: those
states already agreed.

Then, after the fix, **one still failed - and it was my test, not the code.**
`test_the_switch_line_agrees_with_the_startup_line[cannot call tools]` compared the startup line
against the switch line *of the same run*, with `big:70b` tool-capable and `small:1b` not. The
startup line said `web on`; the switch line said `no tools - this model cannot call them`, which
correctly says nothing about the web.

Those two lines describe **different models**, and two models may legitimately differ. The
criterion is "a model that cannot call tools reads the same after a switch as it does at
startup" - the same model, both ways round. So the comparison is now **switching *to* a model
against starting *on* it**, in two runs. That is a stronger test than the one I wrote, and it
came from the criterion disagreeing with my code rather than the other way round.

## Live, against the two lines that started this

```
$ AXIOM_DEBUG_MAX_CONTEXT=3000 axiom --model gemma4:e2b
axiom: gemma4:e2b at http://localhost:11434 (context: 3000 tokens, debug override, 7 tools including web)
axiom: now qwen2.5:7b (context: 3000 tokens, debug override, 7 tools including web)

$ axiom --model gemma4:e2b --no-web
axiom: gemma4:e2b at http://localhost:11434 (context: 131072 tokens, 5 tools, web off)
axiom: now qwen2.5:7b (context: 32768 tokens, 5 tools, web off)
```

Both gaps closed. Note the second: the window still *follows the model* - 131072 to 32768 -
while `web off` is carried. Agreement was not bought by reporting a stale number, which
`test_the_window_still_follows_the_model` pins.

## Break-and-watch

Removing the two arguments from the `note_switched` call turns **6 red**. Restored, full suite
re-run green.

## Status — all 12 criteria

| criteria | status |
|---|---|
| AC 1–12 | `attempted` |

Not `met-with-evidence`. This is the cycle that wrote the code.

## Cycle 2 will

Cold-read all 12 from GitHub before the diff and before this log. Where to attack:

- **AC 4** - the enumeration above claims `announce` says six things and no more. Verify against
  the source rather than against this table. Is there a caller-side fact - something
  `note_servers` says at startup - that belongs to the session and is not repeated on a switch?
- **The `facts()` parser** - it strips `debug override` by string replacement before splitting.
  Could it mis-parse a state, and so make two lines look equal when they are not?
- **AC 3** - `test_the_window_still_follows_the_model` hard-codes 32768 and 4096. Is that
  asserting the fix or the fixture?
- **The six survivors** of the break, each with a verdict.

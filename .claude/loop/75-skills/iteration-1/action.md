# Action

**Re-run the live measurement with the corrected instrument, and record every number.**

Cycle 8's scores came from a test that counted only structured tool calls and so scored
`qwen2.5-coder:7b` 0/10 for announcing its call as text - the exact case #34 exists to
handle. `_asked_for_the_skill` now passes the reply through `call_from_text` the way a
session does. **All six scores were retracted, not just the wrong one**, because an
instrument found wrong on one input is not trusted on the others.

    uv run pytest -m live -q -s

It takes about seven minutes. Record all six rows in the log, including `gemma2:2b` as
"no tool support" - AC 16 is met by writing the number down, not by reaching one.

**Expect `qwen2.5-coder:7b` to land low but not at zero.** Three diagnostic runs showed it
using two shapes: `{"name": "invoke_skill", "arguments": {"name": "release-checklist"}}`,
which `call_from_text` recognises, and `{"name": "release-checklist", "arguments": {}}`,
which it correctly does not - a skill name is not a tool name. **A low score there is a
real result and goes in as one.** Do not loosen `call_from_text` to make the number better;
that guard refuses unknown names for #34's reasons and this is not the story that changes
it.

**If a model scores badly, the preamble is the only lever** - and cycle 2 put it under
#68's rule: change it, re-measure *every* model, and keep the change only if it improves at
least one and worsens none. One re-measurement is seven minutes, so at most one attempt this
cycle. If the first attempt does not clear that bar, revert it and record both sets of
numbers.

**Then take the cheap remainder**, in this order, as time allows: AC 44 (exit unchanged),
AC 43 (no skill failure ends the session), AC 40 (an unreadable file reported), AC 31 and
AC 32 (a skill written or deleted in one run is there or gone in the next), AC 25 (files
beside SKILL.md are not loaded), AC 14 (the model's invocation shown as a tool call - true
already, untested).

Leave AC 29, AC 34 and AC 35 last. They touch compaction and the window, and each needs a
session driven far enough to compact - more setup than the other seven together.

First thing to tackle: **the re-measurement**, because it is the only thing in the story
that costs wall-clock time rather than thought, and the fail-safe is 21:30.

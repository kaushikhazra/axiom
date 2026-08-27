# Goal

Let the line said after a model switch carry the same facts the startup line carried - meeting
every one of the 12 acceptance criteria on GitHub issue #56.

#49 AC 16 asks that a switch say **how many** tools the new model has. That is exactly what
landed. The startup line says more than that, and the switch line does not:

```
startup:  gemma4:e2b at http://localhost:11434 (context: 3000 tokens, debug override, 7 tools including web)
switch:   now qwen2.5:7b (context: 3000 tokens, 7 tools)
```

Two facts go missing.

**The web state.** With `--no-web` the startup line says `5 tools, web off` and the switch line
says `5 tools`. After a switch there is nothing on screen saying the web is still off - the tool
count is the only hint, and reading it requires knowing what the count would be otherwise.

**The debug override.** After a switch, `3000 tokens` reads as the new model's own window. It is
not; it is forced. This is the more damaging of the two, because anyone debugging a compaction
problem would take it at face value, and it is the exact figure they would be reasoning from.

Neither is a bug against AC 16 as written. Both are things a person reading the two lines
together expects to line up, and they do not. Found 2026-08-27 by Kaushik reading a real
session's transcript - the two lines sat a few rows apart and the gap was visible in seconds.
**No test would have produced it: each line is individually correct, and nothing asserts they
agree.**

Done when: all 12 criteria of #56 are met, each with evidence recorded in a cycle log; the suite
is green and hermetic; and the golden transcript's change is accounted for line by line.

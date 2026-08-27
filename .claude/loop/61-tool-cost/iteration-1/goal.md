# Goal

Let a user know what their tools cost before they have said anything - meeting every one of the
12 acceptance criteria on GitHub issue #61.

The figure exists. `note_servers` computes it and prints
`tools cost about N tokens per request, M% of the window`. But it is inside a function about
**MCP servers**, and that function returns early when none are attached:

```python
if not connected and not problems:
    return
```

So the line is only ever seen by a user who happens to have configured an MCP server. Everyone
else is told `7 tools including web` and nothing about what those seven cost.

Measured on this machine:

```
7 built-in tools   653 tokens
standing prompt    154 tokens
                   807 tokens - 40% of a 2000-token window, before a word is typed
```

Found 2026-08-27 during the first manual pass. A session forced to a 2000-token window compacted
twice in consecutive turns, and the reason was invisible: the startup line said `2000 tokens`
and the conversation actually had about 1200. **#43 AC 13 asked that "the user can see what the
declared tools cost", and it was built inside the MCP story - so it only ever applies when a
server is attached.** The built-ins have always looked free and never were.

#56's cold read settled the boundary: of everything printed at startup, the cost line is the one
fact a model switch can make stale, because declarations follow the model. That is AC 10 here.

Done when: all 12 criteria of #61 are met, each with evidence recorded in a cycle log; the suite
is green and hermetic; and the golden transcript's change is accounted for line by line.

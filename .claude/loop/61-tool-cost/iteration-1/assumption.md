# Assumption

Standing inputs. These are given - do not re-derive them, and do not spend a cycle deciding
them.

## The codebase this lands in

Rows 1 to 13 merged. **505 tests, green and hermetic** at scaffold time.

- **`terminal.note_servers(connected, problems, bounds, cost, window)`** owns the line today,
  and returns early: `if not connected and not problems: return`. That early return is why the
  cost is invisible without MCP. It also prints the per-server counts, the bounds line, and the
  problems - **none of which this row should move.**
- **`_chat` computes the cost** as
  `compaction.estimated_tokens([{"role": "system", "content": json.dumps(d)} for d in run.declarations or []])`
  and passes it in. **The standing prompt is not in that sum**, and it should be: it rides in
  every request too, held outside `messages` deliberately (#42's reason), and it is 154 tokens
  on this machine.
- **`terminal.announce(...)`** is the startup line and now shares `_room`/`_can_do` with
  `note_switched` after #56.
- **`terminal.note_switched(model, context, tools, overridden, web)`** - the last two are
  **required**, by #56's cold read. Anything added here should follow that rule.
- **`compaction.estimated_tokens(messages)`** is the measurement the size checks use. Divides
  by four. `compaction.too_large` divides by three - **they are different**, and #43's log
  records the system prompt being quoted at 56, then 163, before being measured at 205 by yet
  another route. AC 9 exists because of that history.
- **`tools.system_prompt(limits)`** builds the standing prompt; `_chat` holds it as
  `instructions` and prepends it in `to_send`.
- **`Running.declarations`** is what actually goes to the model, after web filtering and server
  tools are merged. It is the right input for the cost.
- **`StubBackend`** takes `models`, `capable`, `infos`, `listing`; records `asked_about`,
  `capability_asks`, `options`, `tools_sent`.

## Measured 2026-08-27

Do not re-derive; recompute in tests rather than hard-coding.

```
7 built-in tools   653 tokens
standing prompt    154 tokens
total              807 tokens   = 40% of a 2000-token window
```

With the tiny MCP server attached, the reported figure was 959 tokens for 11 tools, 3% of a
32768 window.

## Given

- **`requires-python = ">=3.12"`; the venv is 3.14.3.** `uv` and pytest. No new dependency.
- **The repo's own rules apply**: KISS over structure, one command per shell invocation,
  nothing committed under a `temp` name, project-local `.tmp/`, loop files stay in this folder
  while code stays in `src/` and `tests/`.
- **The branch is `feature/61-tool-cost`.** Commits reference #61.
- **`master` is protected by a hook.** Everything lands on the branch and merges by PR.
- **Two rows follow this one** - #62, then #60. On exit, hand over per the queue.
- **One cron drives the whole queue.** Marking the next row running *is* the handover. **Never
  delete it.**

## Decided - do not reopen

- **The cost line stops depending on MCP.** It is a fact about the session, not about servers.
- **The standing prompt is included** in the figure. It rides in every request; leaving it out
  understates the answer by a fifth on this machine, and the user cannot act on the difference.
- **The figure comes from `compaction.estimated_tokens`** - the same measurement the size checks
  use - so the line cannot disagree with the behaviour it describes. Accuracy is worth less than
  agreement here.
- **`note_servers` keeps everything else.** Per-server counts, bounds, problems. This row moves
  one line out, not the function.
- **#43 AC 13 is widened, not contradicted.** It asked that the cost be visible; it was written
  inside the MCP story and inherited its scope.
- **After a switch the figure follows the new model** (AC 10), which #56's cold read identified
  as the one startup fact a switch can stale.

## Carried forward, worth not relearning

- **A default that happens to be right hides a broken caller.** #56. This row prints a *number*,
  and 0 is plausible - be deliberate about what a missing figure looks like.
- **Name the survivors of the break.** #56's three coincidences were found only by naming them.
- **An assertion a wrong implementation also satisfies proves nothing.** #57 AC 7.
- **Read criteria literally, against states nobody had in mind.** #55 AC 1 against AC 7.
- **Check which function a number came from.** The system prompt was quoted at 56, then 163,
  then measured at 205 - three routes, three answers.
- **Fix every stub before regenerating the transcript.**

# Assumption

Standing inputs. These are given - do not re-derive them, and do not spend a cycle deciding
them.

## The codebase this lands in

Rows 1 to 12 merged. **490 tests, green and hermetic** at scaffold time.

- **`terminal.announce(model, host, context, overridden, tools, web)`** is the startup line. It
  reports, in order: the model, the host, the context (with `, debug override` appended when
  `overridden`, or `Ollama default` when the context is None), and one of four tool phrasings -
  `no tools - this model cannot call them` (None), `tools off` (0), `N tools including web`, or
  `N tools, web off`.
- **`terminal.note_switched(model, context, tools)`** is the switch line, and takes **neither
  `overridden` nor `web`**. That is the whole defect. It says `now {model} (context: {room},
  {can_do})` with `room` being `Ollama default` or `N tokens`, and `can_do` being
  `no tools - this model cannot call them`, `tools off`, or `N tools`.
- **The two build their phrasings independently**, which is how they drifted. Whether that is
  worth unifying is cycle 1's decision to make and record.
- **`_switched_to` calls `note_switched(fresh.model, fresh.context, fresh.offered)`** and has
  `settings` in scope, so `settings.debug_max_context is not None` and `settings.web_enabled`
  are both available without threading anything new through.
- **`Running.offered`** is the tool count: `len(declarations)`, or 0 when tools are off, or None
  when the model cannot call them.
- **`_prepare` applies `settings.debug_max_context`** to the window, so after a switch the
  context genuinely *is* the override - the line just does not say so.
- **The host is not on the switch line and should not be.** A switch cannot change it and the
  startup line already named it (AC 11).
- **`StubBackend`** takes `models`, `capable` (per-model tool support), `infos` (per-model
  `model_info`), `listing`; records `asked_about`, `capability_asks`, `options`, `tools_sent`.

## The defect, as observed

2026-08-27, first manual pass, from a real transcript:

```
startup:  gemma4:e2b at http://localhost:11434 (context: 3000 tokens, debug override, 7 tools including web)
switch:   now qwen2.5:7b (context: 3000 tokens, 7 tools)
```

and with `--no-web`:

```
startup:  gemma4:e2b at http://localhost:11434 (context: 101801 tokens, 5 tools, web off)
switch:   now qwen2.5:7b (context: 32768 tokens, 5 tools)
```

Both confirmed live at the time.

## Given

- **`requires-python = ">=3.12"`; the venv is 3.14.3.** `uv` and pytest. No new dependency.
- **The repo's own rules apply**: KISS over structure, one command per shell invocation,
  nothing committed under a `temp` name, project-local `.tmp/`, loop files stay in this folder
  while code stays in `src/` and `tests/`.
- **The branch is `feature/56-same-facts`.** Commits reference #56.
- **`master` is protected by a hook.** Everything lands on the branch and merges by PR.
- **Three rows follow this one** - #61, #62, #60. On exit, hand over per the queue.
- **One cron drives the whole queue.** It reads `queue.md` for whichever row says `running`.
  Marking the next row running *is* the handover. **Never delete it.**

## Decided - do not reopen

- **The switch line gains the web state and the override note.** Those are the two facts
  observed missing.
- **The host stays off it.** AC 11 says so, and a switch cannot change it.
- **The wording matches the startup line's** for the same state, because AC 5 to AC 8 are about
  the two agreeing. Whether that is achieved by sharing a helper or by duplicating strings is an
  implementation choice - but if duplicated, a test must compare the two lines against each
  other rather than against hard-coded text, or they will drift again exactly as they did.
- **#49 AC 16 is widened, not contradicted.** A comment saying so is already on that issue.

## Carried forward, worth not relearning

- **Assert one line against the other.** A test hard-coding both sides drifts with them and
  cannot catch the thing this row exists to fix.
- **Two settings per fact**, or the test proves a word can be printed rather than that it
  follows anything.
- **An assertion a wrong implementation also satisfies proves nothing.** #57 AC 7, #48 AC 33,
  #49 AC 25 and AC 27.
- **Read criteria literally, and against states nobody had in mind.** #55's AC 1 and AC 7
  disagreed over an empty file and only a literal reading found it.
- **Fix every stub before regenerating the transcript.**
- **A `sed`/`.replace()` that does not match reports success.** Grep after scripted edits.

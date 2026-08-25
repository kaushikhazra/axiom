# Action

Finish the fifteen criteria cycle 2 did not close. Its log has the split; do not re-derive it.

## 1. AC 19 and AC 20 — the timeouts must be settings, not constants

`START_TIMEOUT` and `CALL_TIMEOUT` are module constants in `servers.py`. The criteria ask for
each to have a default, be changeable on the command line **and** in the environment with the
command line winning, and for every value in force to be visible at startup.

- Mirror `--command-timeout` and `--fetch-timeout` exactly; that pattern is established and
  #41 already proved the model can be told about them without drift.
- **Visible at startup** is AC 20, and it is the half that gets forgotten.

## 2. AC 10, 11, 12 — selection

`ServerSpec.tools` already filters and a missing tool already reports. Test all three,
including the case that matters: a named tool the server does not offer is reported **by
name**, and the other named tools are still declared.

## 3. AC 22, 23, 24, 25 — when a server does not work

- **AC 22** — a server still not ready at the bound is given up on, and axiom says so rather
  than waiting. A server that starts and never answers `list_tools` is the case; our own
  script can be made to hang.
- **AC 23** — a call past its bound is stopped, the model told, the turn carries on.
- **AC 24** — a server that dies mid-session fails **only its own** tools. Kill the subprocess
  with `psutil` and check a built-in still works in the same session.
- **AC 25** — no failure of any kind ends the session or discards the conversation.

## 4. AC 26, 27, 28 — leaving

**This is where the shortcut will be tempting.** `CLAUDE.md`'s clause is explicit: the server
is a script this repo owns, run by the same interpreter. `tests/mcp_server.py` already exists.

- **AC 26** — every server is stopped on every route out: `/exit`, `/quit`, end of input,
  Ctrl-C. Drive `main()` by each and check with `psutil` that the children are gone.
- **AC 27** — including through a failure. Cycle 1 measured that a hard kill leaves no
  survivors *by inheritance* — the server exits when its stdin closes. **Proving today's
  behaviour is not the same as owning it**, so the test asserts the outcome, and if it ever
  stops being free `tools._kill_tree` is there.
- **AC 28** — the exit status is unaffected by anything a server did.

## 5. AC 4, 9, 13 — the rest

- **AC 4** — the user is told while servers are starting, rather than facing a silent pause.
  Cheap, and it belongs in `terminal.py` with every other print.
- **AC 9** — each run starts its own servers, nothing carries over. Two runs, different pids.
- **AC 13** — before any conversation, the user can see what the declared tools cost against
  the context window. Computable from the declarations; #42 measured the system prompt at 205
  tokens for the same reason. Decide where it goes and say why.

## 6. Prove nothing moved

- Full suite and the hermeticity command. **294 is the floor**, and it must still pass with
  no MCP server anywhere.
- `diff .tmp/transcript-baseline-43.txt tests/baseline/transcript.txt` — **byte-identical**
  with nothing configured. Check for removed lines explicitly.

## Record

Status for all 30, and be explicit about anything still not started. Then write cycle 4's
`action.md` — the cold check: criteria from GitHub before the diff and before any log,
attacking each rather than confirming it. That pass has found a real defect in three
consecutive issues.

**Write no questions into it.** Decide, record the decision and the reasoning, carry on.

# Action — cycle 1

**Survey and record. Do not write code.**

#43 built the MCP layer and it works. A cycle that starts adding a transport before anyone has
looked at what the installed SDK offers is guessing at an import name, and the guess will be a
transport that was deprecated two releases ago.

## Before anything else, three checks

1. **`git status`** and **`git branch --show-current`** — must be `feature/81-remote-mcp`.
2. **`gh issue view 81`** — the criteria, read before the code and before this file.
3. **Nothing of this loop's is already running.** Check for stray python processes before
   starting anything. `assumption.md` says why.

## 1 — Survey the SDK, and write down what you read

- Which client transports the **installed** version offers for a server reachable over the
  network, what each is called, and which the SDK's own documentation points at now.
- **Record the version.** A finding about "the SDK" that does not say which one is a finding
  with a shelf life of one release.
- Whether any of it needs a dependency axiom does not already have. `assumption.md` says none
  should; if one does, that is a finding for the log and a justification in `pyproject.toml`,
  not a quiet addition.

Read it out of the installed package, not out of memory.

## 2 — Read what #43 built, and find where the seam is

`src/axiom/servers.py`. Specifically:

- where `StdioServerParameters` and `stdio_client` are constructed — that is the only place
  that should learn there are two kinds;
- what `Servers` does on start, on call, and on stop, and **which of those steps are about a
  subprocess** — those are the ones AC 3 says a remote entry must not reach;
- how `SEPARATOR` routing works, because AC 8 rides on it and #43's cycle 4 found it broken for
  a server whose name contained the separator.

Write the seam down in the log as a sentence: *"the one function that has to learn there are
two kinds is X, and everything below it stays as it is."* If that sentence cannot be written,
the design is not understood yet and cycle 2 will find out the expensive way.

## 3 — Pin AC 22 and AC 3 before anything can break them

Two tests, both of which should pass today:

- **AC 22** — a session with no MCP configured is byte-for-byte unchanged. The golden
  transcript already says this; a test that says it *for this row* is what goes red when a
  remote code path starts costing something on every run.
- **AC 3** — nothing is spawned for an entry that names no command. Today no such entry can
  exist, so pin the half that can be pinned: that `Servers` spawns exactly one subprocess per
  configured command and none otherwise. **Break it and watch it go red.**

## 4 — Name the AC 17 decision, do not answer it

> A plain-text address is refused, or the user is told the traffic is not encrypted.

Two acceptable outcomes and they lead to different features. `assumption.md` records the leaning
— refusing `http://` outright makes this useless for someone running a server on their own
machine — but **cycle 2 decides with the survey in hand**, and records the reasoning under a
heading that says it was a decision.

## 5 — Establish the baseline numbers

- `uv run pytest` — count, pass, wall-clock. Expect **876 passed, 1 deselected, ~89s**.
- `tests/baseline/transcript.txt` — record that it is untouched.
- `uv run --no-sync python .claude/loop/cited.py tests/test_mcp.py` — what #43 already claims,
  so this row does not write a second test for something already covered.

## Do not

- Write or change any code in `src/`.
- Fetch anything. No `npx -y`, no `uvx`, nothing downloaded at test time.
- Contact a hosted server, or need a real secret.
- Start a server on a fixed port.
- Leave a process running. Check before you exit.
- Regenerate the baseline.
- Use a heredoc for anything containing a backslash escape.
- Merge.

## Record

`logs/cycle-1.md`, per `observe.md`. Then write `action.md` for cycle 2 from what the survey
showed.

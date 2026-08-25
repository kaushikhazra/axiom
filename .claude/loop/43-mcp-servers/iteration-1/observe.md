# Observe

Record each cycle:

- A status token for **every one of #43's 30 criteria**: `not-started` / `attempted` /
  `met-with-evidence` / `blocked`. All thirty get a token every cycle, even "no change."
  Cite them as "AC 14".
- How far that moved from the last cycle, and what moved it.
- What is still missing, and whether it can be closed from here at all.
- Any assumption that changed.

## The safety rules bind this loop specifically

`CLAUDE.md`'s testing section has a clause written for #43. It is not advisory:

- **A test never fetches a server.** No `npx -y`, no `uvx`, no package downloaded at test
  time. That dependency is someone else's release, pulled over the network, running as
  whoever ran pytest.
- **Prefer the in-memory transport.** The SDK connects a `Client` straight to a server object
  in the same process - no subprocess, no port, no network. Nearly every criterion should be
  settled that way, and it keeps the suite green with nothing installed and nothing running.
- **Where a criterion genuinely needs a real process** - AC 26 and AC 27 are about processes
  outliving axiom and cannot be proved in-memory - the server is a script this repo owns,
  under `tests/`, run by the same interpreter, working directory set to the sandbox. Our own
  code, reviewed like any other file here.
- **No test contacts a hosted server or needs a real secret.** #43 is stdio-only, so nothing
  legitimate requires one. AC 14 to AC 16 are about substitution and redaction, and a made-up
  variable holding a made-up value proves both.

**AC 26 and AC 27 are where the shortcut will be tempting**, because pointing at a real
server is the fastest way to get a process to kill. That is the moment to write the script.

## What counts as evidence

- **AC 26 and AC 27 need a real subprocess.** "No server process outlives axiom" cannot be
  shown by an object in the same process. Start one, kill axiom by each route, and check with
  `psutil` that the child is gone.
- **AC 3, 4, 5 and 8 need a server that really speaks the protocol.** In-memory is fine - it
  is a real client and a real server, just not a real pipe.
- **AC 1, 2, 29 and 30 are about nothing being configured**, which is the state the whole
  existing suite already runs in. The golden transcript is the instrument.
- **A criterion about a secret is settled with a made-up one.** Never a real token.

## Where this will be tempting to cheat

**AC 6 - "every tool carries its server's name".** The easy version prefixes the string. The
criterion is that a collision *cannot happen* - with a built-in tool, or with another
server's tool. Prove the impossibility, not the prefix.

**AC 13 - "the user can see what the declared tools cost".** Against the context window, and
#42 measured the system prompt at 205 tokens for exactly this reason: fixed costs are the
ones that quietly eat the budget. A count of tools is not a cost.

**AC 16 - "no secret appears in the startup line, in any error, or in anything the model is
told".** Three places, and the third is the one that gets missed. A server that fails to start
often reports its own command line in the error.

**AC 29 - "exactly what they are today".** The transcript is the instrument, and it is
byte-for-byte. Not "no meaningful change".

## Standing checks

- **The full suite is re-run in every cycle that changes code**, and the result recorded.
  The baseline is **272 tests, green** at scaffold time.
- **The suite must stay green with no Ollama, no network, and no MCP server**, and must not be
  changeable by the environment:
  `env AXIOM_HOST=http://127.0.0.1:1 AXIOM_MODEL=nonsense:99b AXIOM_DEBUG_MAX_CONTEXT=7 uv run pytest -q`
- **The golden transcript is the behaviour record.** Copy it aside in cycle 1. AC 29 is
  measured by it.
- **Before regenerating the transcript, run `diff` and read all of it.** #41 cycle 2
  regenerated off pytest's assertion summary - which names the *first* differing index and
  reads like it names the whole difference - and destroyed two compaction scenarios. #42
  cycle 4 checked `grep -c "^<"` for removed lines and confirmed the diff was purely
  additive. Do that.
- **A stub that contradicts the thing under test proves nothing.** #40 found `given_page`
  announcing `text/plain` over HTML; #41 found `StubClient` reporting `prompt_eval_count=1`
  whatever it was sent. Both had passed for two issues.
- **A scenario whose name does not match its behaviour is worse than no scenario.** Three
  were corrected in #42 for exactly this.
- If a criterion cannot be met as written, say so plainly and say why. #35 replaced one, #32
  amended three, and #40, #41 and #42 each had one broken by the cold read. That is an
  acceptable outcome; quietly reinterpreting one is not.

## The cycle that writes the code never declares it done

A separate cycle checks, reading the criteria from GitHub **before** the diff and before the
previous log. **Attack each criterion rather than confirming it.**

This has now found a real defect in **three consecutive issues**, every time after the
implementing cycle had written `met-with-evidence` beside it:

- #40 AC 7 — a typeless PNG returned its bytes as content and was counted as a source.
- #41 AC 9 — the retry block compared whole result strings, so a pid in the output defeated
  it and the criterion was decorative.
- #42 AC 3 — the fix compacted away the user's own message; the model was sent a summary of
  the question and no question, and answered something it had never seen.

Each was found by a hostile input. None by rereading code.

## Goal check

- **Met** - all 30 criteria `met-with-evidence`, the lifetime ones against a real subprocess,
  the suite green and hermetic with nothing installed, the transcript accounted for.
- **Not met** - report which criteria moved and which did not, and write the next action.
- **Answer did not move** - report the flat result and stop. Do not run another variant.

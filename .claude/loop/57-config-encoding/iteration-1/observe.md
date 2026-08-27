# Observe

Record each cycle:

- A status token for **every one of #57's 9 criteria**: `not-started` / `attempted` /
  `met-with-evidence` / `blocked`. All nine get a token every cycle, even "no change."
  Cite them as "AC 4".
- How far that moved from the last cycle, and what moved it.
- What is still missing, and whether it can be closed from here at all.
- Any assumption that changed.

## Where this will be tempting to cheat

**AC 1 - a file with a mark is read.** The cheat is a test that writes the mark with
`"\ufeff" + text` and reads it back through the same code. That proves the round trip, not the
criterion. **Write the bytes** - `b"\xef\xbb\xbf" + payload` - because the criterion is about a
file some other program wrote, and bytes are what that program leaves behind.

**AC 4 - a mark never becomes part of a value.** This is the one a careless fix breaks. Stripping
the mark at the top level and decoding the rest as `utf-8` leaves `\ufeff` glued to the first
key or the first value, so a server ends up named `\ufefftiny` and its command unrunnable - and
every test that checks the servers parsed would still pass, because one did. Assert on the exact
name, the exact command, and the exact argument strings.

**AC 5 and AC 6 - what axiom writes.** `write_choice` reads, mutates and rewrites. Feed it a
file that already has a mark and assert the file it leaves has **none**, and that reading it
back gives one dict rather than a mark stuck to a host key.

**AC 7 and AC 8 - still failing when it should.** The risk of a permissive decoder is that it
starts accepting things it should reject. A file of pure rubbish, a JSON array where an object
is wanted, and a file with no `mcpServers` section must each report exactly what they report
today, word for word.

**AC 9 - the same on every platform.** Nothing in the fix may branch on the platform. Grep for
it; a test cannot see a branch that only fires elsewhere.

## What counts as evidence

- **Bytes, not strings.** Every criterion about a mark is settled by writing real bytes to a
  real file in `tmp_path` and letting axiom read it as it would any other.
- **Both files.** `config.read_servers` and `models.read_choice`/`unreadable`/`write_choice`.
  A fix to one and not the other meets half the criterion and looks complete.
- **The message is unchanged.** AC 7 is byte-for-byte against what is reported today, not
  "still reports something".

## Standing checks

- **The full suite is re-run in every cycle that changes code**, and the result recorded. The
  baseline is **453 tests, green** at scaffold time, 2026-08-28 00:21 IST.
- **The suite must stay green with no Ollama running**, and must not be changeable by the
  environment:
  `env AXIOM_HOST=http://127.0.0.1:1 AXIOM_MODEL=nonsense:99b AXIOM_DEBUG_MAX_CONTEXT=7 uv run pytest -q`
- **The golden transcript must not change.** This row alters how bytes are decoded and nothing
  a user sees. Copy it aside in cycle 1 and confirm it is byte-identical at the end. A
  regeneration here would be a mistake, not a decision.
- **A stub that contradicts the thing under test proves nothing.** This row exists *because*
  every test wrote its config the one way that cannot fail. Assume there are others.
- **Ask whether each test could pass if the feature did nothing**, then break the feature and
  watch it go red. Record the counts.
- If a criterion cannot be met as written, say so plainly and say why.

## The cycle that writes the code never declares it done

A separate cycle checks, reading the criteria from GitHub **before** the diff and before the
previous log. **Attack each criterion rather than confirming it.**

This has found a real defect in **six consecutive issues** - #40 AC 7, #41 AC 9, #42 AC 3,
#43 AC 6, #48 AC 33, #49 AC 25 and AC 27 - every time after the implementing cycle marked it
met, and every time by a hostile input rather than by rereading code.

**Two of the most recent were a different shape**: not wrong code, but a *criterion read too
loosely by the cycle implementing it*, with the test then written from the implementation
rather than from the issue. Read the issue text first, and read it literally.

## Goal check

- **Met** - all 9 criteria `met-with-evidence`, suite green and hermetic, transcript
  byte-identical, and a PowerShell-written file read without complaint.
- **Not met** - report which criteria moved and which did not, and write the next action.
- **Answer did not move** - report the flat result and stop. Do not run another variant.

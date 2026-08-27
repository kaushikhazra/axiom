# Cycle 1 — reproduced from bytes, fixed, and proved against PowerShell

2026-08-28 00:21–00:52 IST. Fail-safe 04:21 IST.

**471 tests, green and hermetic** (was 453). 18 new in `tests/test_encoding.py`.
**Golden transcript byte-identical**, as this row requires.

## The failing test came first, and that mattered

`action.md` asked for the defect reproduced from real bytes before touching `src/`, and it
earned its place twice.

**13 of 18 failed before the fix.** Not 18 - and the five that passed were the ones asserting
things that were already true, which is the correct shape. The suite could not have found this
on its own: 453 tests over these two files, every one writing config with
`Path.write_text(encoding="utf-8")`, which never emits a byte order mark.

**One of the 13 was my own test being wrong**, and watching it fail is what caught it.
`test_an_unmarked_file_still_reads` failed on a file with *no* mark, which cannot be an
encoding defect. The shared fixture carried `"env": {"TOKEN": "${MADE_UP_TOKEN}"}`, and an
unset reference is reported as a problem - correctly, by #43's design. So `problems == ()` was
asserting against a list that could never be empty, for a reason with nothing to do with this
row. Split into `SERVERS_WITH_ENV`, used only by the test that is about a variable.

Had the fix gone in first, that test would have gone green with the rest and the fixture would
have stayed wrong - asserting nothing, for as long as the file lives.

## The fix

`encoding="utf-8-sig"` at four reads: `config.py:109`, `models.py:94`, `models.py:115`,
`models.py:136`. Writes stay `utf-8`.

**Every remaining `encoding="utf-8"` under `src/` accounted for**, so a later cycle need not
wonder whether one was missed:

| where | why it stays |
|---|---|
| `models.py:144` | the write. axiom emits no mark of its own. |
| `tools.py:155,161,173,179` | arbitrary user files opened by a tool, not axiom's config. Out of scope by decision - a mark there decodes to a character rather than raising. |
| `servers.py:207` | a handle on devnull. |
| `terminal.py:22` | console output, not a file. |

## Decision — the decoder removes the mark, nothing else does

Recorded because the alternative is the version that looks fine and is not. Stripping the mark
from decoded *text* leaves `\ufeff` glued to the first key: a server named `\ufefftiny`, whose
command cannot be run and whose name never matches a routing lookup - and
`len(servers) == 1` still passes. `utf-8-sig` removes it before `json.loads` sees anything, so
no value can carry one. Four tests assert on exact names, commands, arguments, env values and
host keys rather than on counts.

## Proved against the thing that started it

Not a Python string with a mark prepended. A file written by PowerShell's own default:

```powershell
'...' | Set-Content .\.axiom\mcp.json -Encoding utf8
(Get-Content .\.axiom\mcp.json -Encoding Byte -TotalCount 3) -join ','
239,187,191
```

Then axiom against it:

```
axiom: starting 1 MCP server...
axiom: qwen2.5:7b at http://localhost:11434 (context: 32768 tokens, 11 tools including web)
axiom: tiny: 4 tools
```

That is the exact file, written the exact way, that failed at 17:03 yesterday with
`Unexpected UTF-8 BOM`.

## Break-and-watch

Reverting all four reads to `utf-8` turns **12 red**. Restored, and both files re-grepped to
confirm the restore landed - 1 in `config.py`, 3 in `models.py`.

## Status — all 9 criteria

| criteria | status |
|---|---|
| AC 1–9 | `attempted` |

Not `met-with-evidence`. This is the cycle that wrote the code. Every criterion has a test and
the live proof is above, and the verdict still belongs to a cycle that has not read this log.

## Cycle 2 will

Cold-read all 9 from GitHub before the diff and before this log. The places to attack, given
what this cycle had to fix in itself:

- **AC 4** is the one a careless fix breaks. Is there a path where a mark reaches a value that
  these four tests do not cover - a nested key, a `tools` list entry?
- **AC 7 and AC 8** assert today's exact words. Confirm against the *current* message text, not
  against what this log says it is.
- **AC 9** is asserted by grepping for platform branches. Could that assertion pass while a
  branch exists under another name?
- And the standing question: could any of these 18 pass if the feature did nothing?

# Assumption

Standing inputs. These are given - do not re-derive them, and do not spend a cycle deciding
them.

## The codebase this lands in

Rows 1 to 10 merged, plus #52 and #58. **453 tests, green and hermetic** at scaffold time.

- **Four reads decode config as JSON**, and all four are in scope:
  - `config.py:109` - `read_servers`, the MCP file.
  - `models.py:94` - `read_choice`, the remembered model.
  - `models.py:115` - `unreadable`, which decides whether to say the file is broken.
  - `models.py:136` - inside `write_choice`, which preserves other hosts' entries.
- **`tools.py:155` and `tools.py:173` also read with `utf-8`**, and are **out of scope**. Those
  are arbitrary user files read by a tool, not axiom's own configuration. A mark there survives
  decoding as a `\ufeff` character rather than raising, so it is a cosmetic question about
  someone else's file and belongs to its own story if it belongs anywhere.
- **`config.read_servers` returns problems rather than raising** - a bad entry costs that
  server, not the session. `models` does the same with None and a boolean. Neither contract
  changes here.
- **`terminal.note_choice_unreadable` and the `mcp_problems` list** are how a bad file is
  reported. Both stay exactly as they are: this row changes what counts as bad, not what is
  said about it.

## Measured 2026-08-27

Do not re-derive. Confirmed at a Python prompt against the real decoder:

```
utf-8      -> FAILS: Unexpected UTF-8 BOM (decode using utf-8-sig): line 1 column 1 (char 0)
utf-8-sig  -> {'mcpServers': {}}
utf-8-sig on a file with no mark -> {'a': 1}
```

- **`utf-8-sig` reads both forms.** It strips a leading mark if there is one and behaves as
  `utf-8` otherwise. It is a decoder, so the mark is gone before `json.loads` ever sees it -
  which is what keeps AC 4 true without any string surgery.
- **Windows PowerShell 5.1 `Set-Content -Encoding utf8` writes the mark.** So do `Out-File` and
  Notepad. `Set-Content -Encoding ascii` does not, which is the workaround used to unblock
  manual testing and is **not** the fix.
- Python's own `write_text(encoding="utf-8")` never writes one, which is why 453 tests missed
  this entirely.

## Given

- **`requires-python = ">=3.12"`; the venv is 3.14.3.** `uv` and pytest.
- **No new dependency.** `utf-8-sig` is a codec in the standard library.
- **The repo's own rules apply**: KISS over structure, one command per shell invocation,
  nothing committed under a `temp` name, project-local `.tmp/`, loop files stay in this folder
  while code stays in `src/` and `tests/`.
- **The branch is `feature/57-config-encoding`.** Commits reference #57.
- **`master` is protected by a hook** - commits on it are blocked. Everything lands on the
  branch and merges by PR.
- **Five rows follow this one** - #55, #56, #61, #62, #60. On exit, hand over per the queue.

## Decided - do not reopen

- **`utf-8-sig` on read, `utf-8` on write.** Read permissively, write cleanly. axiom emits no
  mark of its own, and a file it rewrites loses the one it came with.
- **No string stripping.** Decoding is where the mark is removed, so no value can carry one.
  A `text.lstrip("\ufeff")` fix is the version that leaves `\ufeff` glued to a server name.
- **Nothing branches on the platform.** A mark is a mark wherever it was written, and a config
  file written on Windows may be read on Linux.
- **The reported problems do not change.** A genuinely malformed file says today's words.
- **`tools.py` is out of scope**, per the note above.

## Carried forward, worth not relearning

- **A stub that contradicts the thing under test proves nothing.** This row *is* that lesson -
  the suite could not fail because every test wrote its config the one way that works.
- **A test can prove the happy path of a criterion and miss the criterion.** Six issues running.
- **Read the issue text literally.** #48 AC 33, #49 AC 25 and AC 27 were all criteria read too
  loosely by the cycle implementing them.
- **A `sed`/`.replace()` that does not match reports success.** Verify scripted edits by
  grepping for what should have changed.
- **The formatter is not the only thing that edits a file.** Verify what landed.

# Action

**Cycle 1 records the baseline, reproduces the defect from bytes, and fixes it.** Small enough
that splitting the fix off would spend a firing to save nothing - but the verdict still belongs
to a later cycle, not this one.

## 1. Baseline

- `env AXIOM_HOST=http://127.0.0.1:1 AXIOM_MODEL=nonsense:99b AXIOM_DEBUG_MAX_CONTEXT=7 uv run pytest -q`
  Expect **453 passed**. Record it.
- Copy `tests/baseline/transcript.txt` to `.tmp/transcript-baseline-57.txt`. It **must not
  change** this row - confirm byte-identical at the end.
- `gh issue view 57`, record all 9 criteria `not-started`.

## 2. Reproduce it from bytes, before touching src

Write a failing test first, because this is the one row where the existing tests are the
problem. In `tmp_path`, with `Path.write_bytes`:

```python
b"\xef\xbb\xbf" + json.dumps({"mcpServers": {...}}).encode()
```

Then `config.read_servers(that_path)`. It must currently return no servers and one problem
naming the mark. **Watch it fail before fixing anything** - a test that was green from the
start would prove nothing here.

## 3. Fix all four reads

`config.py:109`, `models.py:94`, `models.py:115`, `models.py:136` - `encoding="utf-8-sig"`.
Writes stay `utf-8`. Leave `tools.py` alone.

Then **grep for `encoding="utf-8"` under `src/`** and account for every remaining one in the
log, so the next cycle does not have to wonder whether one was missed.

## 4. Cover the criteria that a careless fix would break

- **AC 4** - assert the exact server name, command and each argument. A mark glued to a key
  passes any test that only counts servers.
- **AC 5, AC 6** - `write_choice` over a file that already has a mark: the file it leaves has
  none, and reading it back gives one dict with one host key.
- **AC 7, AC 8** - rubbish, a JSON array, and a file with no `mcpServers` section each still
  report **today's exact words**.
- **AC 9** - grep the diff for any platform branch. There must be none.

## 5. Prove it against the thing that started it

A file written the way PowerShell writes one - real bytes, not a Python string with a mark
prepended - read by axiom without complaint. Record the bytes used.

## 6. Then

Full suite, hermeticity command, and `diff` the transcript to confirm **no change**. Write
cycle 2's action: a cold read of all 9 from GitHub, before the diff and before this log.

## Record

Status for all 9. The failing-test-first evidence. Every remaining `encoding="utf-8"` under
`src/` and why it is right. Whether the transcript moved.

**Write no questions into anything.** Decide, record the decision and the reasoning under a
heading that says so, carry on. The exception is safety, not uncertainty.

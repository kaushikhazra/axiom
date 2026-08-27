# Cycle 2 — implementation

2026-08-27 13:40–14:05 IST. Fail-safe 16:27 IST.

**369 tests, green and hermetic** (was 317). 51 new in `tests/test_models.py`, one new in
`tests/test_config.py`.

## What landed

| file | change |
|---|---|
| `backend.py` | `installed()` on the protocol and `OllamaBackend`. **Does not swallow** - raises `ConnectionLost`, unlike `model_info`/`supports_tools`. |
| `models.py` | New. Sorting, the remembered choice, and `choose()` - the whole decision table as one function returning a `Decision`. Nothing prints. |
| `terminal.py` | The list, the question, three refusals, four announcements, two fatal reports. |
| `config.py` | `DEFAULT_MODEL` deleted. `--model` defaults to `None`; `Settings.model` is `str \| None`. |
| `__init__.py` | `_settle_model()` before anything starts, `_remember()`, `CANNOT_START = 2`. |
| `.gitignore` | `.axiom/model.json` only - never a blanket `.axiom/`. |

## Two things nearly went wrong

**I regenerated a broken golden transcript and caught it in the diff.** `StubClient` in
`test_characterization.py` is a *vendor-level* stub, separate from `conftest.StubBackend`, and
it had no `list`. Regenerating before fixing it wrote a baseline in which every scenario ends
`escaped AttributeError: 'StubClient' object has no attribute 'list'` — a golden master
recording a crash as correct behaviour. Restored from `.tmp/transcript-baseline-48.txt`, fixed
the stub, regenerated.

This is exactly what `observe.md` warns about, and the copy-aside step is the only reason it
was recoverable. **The lesson is narrower than "read the diff": fix every stub before
regenerating, because a transcript regenerated against a broken stub is still a green suite.**

Final diff: **27 added lines, all identical, `grep -c "^<"` = 0.** Every one is
`axiom: using qwen2.5:7b - the only model installed` — AC 17, because the stub host has one
model. No line changed and no line was removed; the startup line itself is byte-identical.

**A scripted replace missed a line.** Resetting the fail-safe clock with `sed` matched only
the dated form `2026-08-27 14:41 IST` and left a bare `14:41 IST` on line 38 saying the
opposite of the line above it. Caught by grepping after the edit rather than trusting the
exit status. The standing note about `.replace()` reporting success applies to `sed` too.

## Decisions made this cycle

- **`installed()` raises where its neighbours swallow.** Recorded in cycle 1; implemented
  here. Without it AC 31 and AC 32 collapse into one message.
- **`sys.exit(2)` rather than a returned status.** The shim does `sys.exit(main())` so both
  work, but only this one is measurable with `pytest.raises(SystemExit)` and only this one
  survives `python -m`.
- **The choice file's path resolves through `_where()` at call time**, not as a default
  argument. A default argument freezes it at import, and there would be no way to point a
  test somewhere harmless — which matters because the path is relative to the working
  directory and the working directory in a test run *is this repository*. An autouse fixture
  in `conftest.py` now redirects it to `tmp_path` for every test.
- **A corrupt choice file is replaced on write, not refused.** It holds a preference. Refusing
  to save because a previous save is corrupt would strand the user with no way back except
  deleting a file nobody told them about.
- **Only a number is accepted at the startup list**, not a name. #49 adds names at the switch
  prompt where there is a command to disambiguate; here, accepting both would make `3`
  ambiguous the day someone installs a model called `3`.

## Live against the real Ollama

Both paths driven against `http://localhost:11434`, five models installed.

Piped, nothing named:

```
$ printf '2\n/exit\n' | axiom
axiom: using gemma2:2b - first installed, nothing was chosen
axiom: gemma2:2b at http://localhost:11434 (context: 8192 tokens, no tools - this model cannot call them)
> I am axiom, a terminal assistant. ...
```

**AC 18 confirmed live**: the `2` reached the model as a message rather than answering a menu.

Interactive, with two refusals then a bare enter:

```
axiom: models on http://localhost:11434
  1. gemma2:2b  (default)
  2. gemma4:e2b
  3. ornith:9b
  4. qwen2.5-coder:7b
  5. qwen2.5:7b
axiom: which model? (enter for the default) 9
axiom: there is no model 9 - type a number from 1 to 5
axiom: which model? (enter for the default) abc
axiom: 'abc' is not a number - type a number from 1 to 5
axiom: which model? (enter for the default)
axiom: remembering this choice in .axiom
axiom: gemma2:2b at http://localhost:11434 (context: 8192 tokens, ...)
```

Sorted, not the host's `modified_at` order. The written file was
`{"http://localhost:11434": "gemma2:2b"}`, correctly ignored by git.

## Finding for Kaushik — the first-installed default is the one model with no tools

Predicted when the assumptions were written; now observed in a real run. `gemma2:2b` sorts
first on this machine and is the only model here that cannot call tools, so a first-ever run
with nothing named and nothing remembered — and **every** piped run in that state — lands on
a model with no tools.

Not changed, per the standing instruction not to quietly sort by something else. It is
announced, it is one keystroke to change, and it is remembered thereafter. **Recorded as a
change-request candidate**, which is the route Kaushik asked for.

## Status — all 38 criteria

| criteria | status |
|---|---|
| AC 1–38 | `attempted` |

Deliberately not `met-with-evidence`. Every one has a test and the suite is green, but this is
the cycle that wrote the code, and it does not get to declare it done. Cycle 3 reads the
criteria from GitHub first and attacks them.

## Cycle 3 will

Cold-read all 38 against the issue text, before the diff and before this log. Specifically
hunt for vacuous tests among the ones that assert on absence — AC 14's four negatives, AC 23,
AC 35, AC 36, AC 37 — by breaking the feature and watching each go red.

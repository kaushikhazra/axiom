# Action

Three criteria remain - AC 7, AC 11, AC 20 - and they are one piece of work, not three. The
duplicated test helpers exist because every test module builds its own client stub; the
per-module tests do not exist because there was nothing to test per module until this cycle;
and AC 7 is unfinished because `main()` still builds its own backend rather than accepting
one. A single shared stub in `conftest.py`, injected into `main()`, closes all three.

Do it in that order.

## AC 7: let `main()` take a backend

`main()` accepts a `ModelBackend` from its caller and falls back to building an
`OllamaBackend` when it is not given one, so the console entry point still works untouched
(AC 3).

Then move the tests that currently patch `axiom.backend.ollama.Client` onto that seam - pass
the stub in instead. When it is done, `grep -rn "setattr.*Client" tests/` should return
nothing, which is how AC 7 is settled: substituting a backend requires no patching of module
globals.

**`psutil.virtual_memory` patching is not in scope.** That is a real dependency of
`context.py`, not the model seam, and AC 7 is about the backend.

Budget note: `src/` is at 446 of 447. This change is worth roughly one line. If it lands over,
take the room from `compaction.py` - two of its docstrings restate mechanics the code shows
directly. Do not touch the KV-cache derivation, the never-re-summarize rationale, the
leading-blank-line explanation, or the `estimated_tokens` note.

## AC 11: one stub, one feed

`feed()` is defined in three test modules and `_chunk()` in three. Move one of each into
`conftest.py` as fixtures or helpers and delete the copies. The stub that `main()` now
receives should live there too - `RecordingBackend` in `test_compaction.py` and `StubClient`
in `test_characterization.py` overlap heavily.

Take the chance to check the rest of AC 11 while in there: any default or literal appearing in
more than one place across `src/` and `tests/`. The host, the model name and the prompt string
are the likely ones.

## AC 20: a test file per module

`config`, `context`, `backend` and `terminal` have no test module of their own. They are
covered incidentally by tests aimed at other things, which is not the same as being tested.

Write the missing ones - small, direct, no live model. `terminal.report_failure` in particular
deserves direct tests: it carries four distinct messages and a leading-blank-line rule that
only the transcript currently pins down, and the transcript would not tell you *which* rule
broke.

**Do not restate what the characterization transcript already covers.** These are unit tests
of a module's own contract, not a second copy of the golden master.

## Record

Full suite plus characterization after each of the three steps. `wc -l` across `src/` against
447 after AC 7's change. Status token for all 20.

If all 20 read `met-with-evidence` and the suite is green, **the goal is met** - follow
`loop.md`'s exit 1: commit, push, open a PR referencing #33, merge it, delete the branch,
delete the cron, and say so.

# Cycle 1 — 2026-08-24 00:22 IST

## Where the artifact stands

`src/` did not exist at the start of this cycle. It does now: `pyproject.toml`, `src/axiom/__init__.py` (14 lines), `uv.lock`. One exchange with a live model works.

**Evidence — the round trip:**

```
$ echo "In one short sentence, what is the capital of France?" | uv run --directory C:/Projects/axiom axiom
> The capital of France is Paris.
```

Real call: `ollama.Client(host="http://localhost:11434").chat(model="qwen2.5:7b", ...)` against the locally installed model. `uv sync` resolved 13 packages, `ollama==0.6.2`.

## Criteria

| AC | State | Evidence |
|---|---|---|
| 1 prompt on start | **met** | `> ` printed above before the reply |
| 2 documented defaults, in `--help` | **not met** | defaults exist as module constants; there is no `--help` |
| 3 message → reply | **met** | transcript above |
| 4 reply in full | **untested** | one short reply is not evidence against truncation; needs a long generation |
| 5 progress while generating | **not met** | nothing is shown; a slow reply looks hung |
| 6 empty line does not call | **not met** | empty input is sent to the model |
| 7 multi-turn, process stays alive | **not met** | exits after one exchange |
| 8 history sent with each message | **not met** | single message list, no history |
| 9 state in-process only | **untested** | nothing persists, but there is no session to speak of yet |
| 10 env var host / model | **not met** | constants only |
| 11 flag beats env beats default | **not met** | no flags |
| 12 effective host/model visible | **not met** | not shown anywhere |
| 13 unreachable host → named error | **not met** | uncaught exception, raw traceback |
| 14 missing model → named error | **not met** | uncaught exception |
| 15 partial output not sold as complete | **untested** | no streaming yet, so no partial state to mishandle |
| 16 failed turn leaves session usable | **not met** | any failure kills the process |
| 17 exit command → status 0 | **not met** | no exit command |
| 18 EOF → status 0 | **not met** | EOF raises `EOFError` |
| 19 Ctrl-C semantics | **not met** | uncaught `KeyboardInterrupt` |

**2 met, 14 not met, 3 untested.**

## Movement

From nothing to a working round trip. The move that did it: `uv init` equivalent + the `ollama` package + 14 lines. No hand-rolled HTTP, per assumption.

## What is still missing, and is it closable

Everything except AC 1 and 3. All of it is closable from here — nothing found in this cycle blocks any remaining criterion. The shape of the remaining work is four independent seams: a REPL with history (7, 8, 9), configuration with precedence (2, 10, 11, 12), error handling (13, 14, 16), and lifecycle/interrupt (6, 17, 18, 19). AC 4, 5, 15 all touch how output is delivered and will likely be settled together by streaming.

## Assumptions that changed

**One did, and it stopped the cycle mid-way.** `assumption.md` said to commit each cycle's work and that plain pushes to `master` are allowed. It did not say where the work happens — and `protected_branch_guard.py` blocks *editing source or test files on `master`* at all, not just pushing. The first `Write` to `src/` was rejected.

Corrected: work for this story happens on `feature/26-ollama-chat`, branched from `master` at `55630af`. `assumption.md` updated to say so. This is a genuine gap in the setup, not a one-off — any future loop that writes code will hit the same guard on cycle 1.

## Goal check

**Not met.** 2 of 19. Next action written.

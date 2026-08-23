# Cycle 3 — 2026-08-24 00:52 IST

## Where the artifact stands

`src/axiom/__init__.py` is 55 lines. Host and model are settings resolving flag → environment → default, `--help` documents both defaults, and every run opens by naming the model and host it is actually using.

**Evidence — `--help` documents the defaults:**

```
$ uv run axiom --help
usage: axiom [-h] [--host HOST] [--model MODEL]

Chat with a local Ollama model.

options:
  -h, --help     show this help message and exit
  --host HOST    Ollama host. Overrides $AXIOM_HOST. Default:
                 http://localhost:11434
  --model MODEL  Model to chat with. Overrides $AXIOM_MODEL. Default:
                 qwen2.5:7b
```

**Evidence — the full precedence chain, three runs:**

```
$ printf '/exit\n' | uv run axiom
axiom: qwen2.5:7b at http://localhost:11434          <- default

$ printf '/exit\n' | AXIOM_MODEL=gemma4:e2b uv run axiom
axiom: gemma4:e2b at http://localhost:11434          <- env beats default

$ printf '/exit\n' | AXIOM_MODEL=gemma4:e2b AXIOM_HOST=http://127.0.0.1:9999 \
    uv run axiom --model qwen2.5-coder:7b --host http://localhost:11434
axiom: qwen2.5-coder:7b at http://localhost:11434    <- flag beats env
```

**Evidence — chat still works after the change:**

```
$ printf 'Say hello in three words.\n' | uv run axiom
axiom: qwen2.5:7b at http://localhost:11434
> Hello, there!
```

## A defect found and fixed inside this cycle

The startup line first used a `·` separator. On the Windows console it rendered as `axiom � gemma4:e2b � http://...` — mojibake, cp1252 against a UTF-8 source. That directly undermines AC 12, whose whole point is that the user can *read* which model answered, so it was fixed in-cycle to a plain-ASCII `axiom: <model> at <host>` rather than deferred.

Worth carrying: this program's output is read in a Windows console. Non-ASCII decoration is not free here, and no test would have caught it — only looking at the output did.

## Criteria

| AC | State | Evidence |
|---|---|---|
| 1 prompt on start | met | `> ` in transcripts |
| 2 documented defaults, in `--help` | **met — new** | `--help` output above |
| 3 message → reply | met | regression run above |
| 4 reply in full | **untested** | replies still short by instruction |
| 5 progress while generating | **not met** | nothing shown |
| 6 empty line does not call | met | cycle 2 |
| 7 multi-turn | met | cycle 2 |
| 8 history sent | met | cycle 2 |
| 9 in-process only | met | cycle 2 |
| 10 env var host / model | **met — new** | run 2 of the precedence chain |
| 11 flag beats env beats default | **met — new** | three runs above, in order |
| 12 effective host/model visible | **met — new** | startup line, now legible on this console |
| 13 unreachable host → named error | **not met** | uncaught exception |
| 14 missing model → named error | **not met** | uncaught exception |
| 15 partial output not sold as complete | **untested** | no streaming |
| 16 failed turn leaves session usable | **not met** | any failure kills the process |
| 17 `/exit` → status 0 | met | cycle 2 |
| 18 EOF → status 0 | met | cycle 2 |
| 19 Ctrl-C semantics | **not met** | uncaught `KeyboardInterrupt` |

**12 met, 5 not met, 2 untested.** Was 8 / 9 / 2.

## Movement

Four criteria closed by `argparse` plus two `os.environ.get` defaults — 26 lines. Precedence came free from `argparse`'s own `default=`, so no precedence logic was written.

The cycle also did what it was chosen to do beyond its own criteria: `--host http://127.0.0.1:9999` is now expressible, which is exactly the handle AC 13 needs.

## Assumptions that changed

None. One fact worth carrying forward, recorded above: the console is cp1252, so output stays ASCII.

## Goal check

**Not met.** 12 of 19. Next action written.

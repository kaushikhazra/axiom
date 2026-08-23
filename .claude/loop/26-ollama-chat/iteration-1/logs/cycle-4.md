# Cycle 4 — 2026-08-24 01:07 IST

## Where the artifact stands

`src/axiom/__init__.py` is 66 lines. Failures are caught, named, and survivable: the message that failed is removed from history, the error goes to stderr, and the prompt returns.

**Evidence — unreachable host, two turns, no traceback:**

```
$ printf 'hello\nstill alive?\n' | uv run axiom --host http://127.0.0.1:9999
axiom: qwen2.5:7b at http://127.0.0.1:9999
> error: cannot reach Ollama at http://127.0.0.1:9999 (Failed to connect to Ollama...)
> error: cannot reach Ollama at http://127.0.0.1:9999 (Failed to connect to Ollama...)
>
```

**Evidence — missing model is named, nothing else answers:**

```
$ printf 'hello\n' | uv run axiom --model does-not-exist:1b
axiom: does-not-exist:1b at http://localhost:11434
> error: model 'does-not-exist:1b' not found (status code: 404)
>
```

**Evidence — a failed turn followed by a real reply, same process:**

```
$ printf 'This first turn should fail.\nSay hello in exactly three words.\n' \
    | uv run axiom --host http://127.0.0.1:11435
axiom: qwen2.5:7b at http://127.0.0.1:11435
> error: cannot reach Ollama at http://127.0.0.1:11435 ([WinError 10053] An established
  connection was aborted by the software in your host machine)
> Hello, there!
>
```

The second reply is a genuine `qwen2.5:7b` generation reaching the real daemon — not a fallback string.

## The test that mattered, and the defect only it could find

A config-level failure (bad host, bad model) is the same failure on every turn, so it cannot evidence "the session survives and the *next* message works". That needs a **transient** failure. Built one: a 30-line proxy on 11435 that closes the first connection and forwards every later one to the real Ollama on 11434. Scratch only — `scratchpad/flaky_proxy.py`, not repo source.

It immediately broke the code written earlier in this same cycle. The first implementation caught `ConnectionError` and `ollama.ResponseError`. That is what the package raises when a connect is *refused* — but a connection dropped **mid-request** surfaces as a raw `httpx.ReadError`, which is not a `ConnectionError` and is not an `OSError`. It escaped as a 60-line traceback and killed the process.

So the criteria that looked met after the first two tests were not: AC 13 named the host only for one of two connection failure modes, and AC 16 was false outright — that failure killed the session rather than leaving it usable.

Fixed by catching `httpx.HTTPError` alongside the other two, and `httpx` is now a declared dependency rather than one relied on transitively through `ollama`.

**Carry forward: two failure paths that look identical to a user are different exception types here.** Testing only the easy one (refused connect) produced two criteria marked met that were not.

## Criteria

| AC | State | Evidence |
|---|---|---|
| 1 prompt on start | met | transcripts |
| 2 documented defaults in `--help` | met | cycle 3 |
| 3 message → reply | met | proxy transcript, second turn |
| 4 reply in full | **untested** | replies still short by instruction |
| 5 progress while generating | **not met** | see below — now with evidence of why it matters |
| 6 empty line does not call | met | cycle 2 |
| 7 multi-turn | met | cycle 2 |
| 8 history sent | met | cycle 2 |
| 9 in-process only | met | cycle 2 |
| 10 env var host / model | met | cycle 3 |
| 11 flag beats env beats default | met | cycle 3 |
| 12 effective host/model visible | met | cycle 3 |
| 13 unreachable host → named error | **met — new** | both connection failure modes name the host |
| 14 missing model → named error | **met — new** | 404 transcript, no fallback |
| 15 partial output not sold as complete | **untested** | no streaming, so no partial state |
| 16 failed turn leaves session usable | **met — new** | error then genuine reply, one process |
| 17 `/exit` → status 0 | met | cycle 2 |
| 18 EOF → status 0 | met | cycle 2 |
| 19 Ctrl-C semantics | **not met** | uncaught `KeyboardInterrupt` |

**15 met, 2 not met, 2 untested.** Was 12 / 5 / 2.

## Movement

Three criteria closed. The move was small — one `try`, three `except` arms, and a `messages.pop()` so a failed turn does not poison history. The cycle's real work was building the transient-failure harness, which is what turned two false "met" marks back into real ones.

## A finding for AC 5, from a discarded attempt

Before the proxy, this cycle tried to induce a failure with a 400,000-character message. It did not fail — it ran for **over five minutes with no output at all** before being killed. That is the exact condition AC 5 exists for: a slow generation is indistinguishable from a hang. It is no longer a hypothetical.

## Assumptions that changed

`httpx` added as a direct dependency. Previously present only transitively via `ollama`; the code now imports it, so it is declared.

## Goal check

**Not met.** 15 of 19. Next action written.

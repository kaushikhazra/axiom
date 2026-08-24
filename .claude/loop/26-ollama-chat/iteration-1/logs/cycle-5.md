# Cycle 5 — 2026-08-24 01:22 IST

## Where the artifact stands

`src/axiom/__init__.py` is 80 lines. The reply streams token by token, and a stream that dies part-way is reported as cut off rather than handed over as an answer.

**Evidence — output arrives progressively, not in one block.** A harness (`scratchpad/arrival.py`) spawns the program, asks it to count to 60, and timestamps every byte as it becomes readable:

```
bytes: 217
first byte at 0.00s, last at 12.97s
spread: 12.97s
distinct bursts (>50ms apart): 169
burst times: 0.00s, 0.26s, 0.33s, 0.41s, 0.48s, 0.55s, 0.62s, 0.69s, 0.75s, ...
```

169 separate arrivals spread over 13 seconds, roughly 70ms apart — one per token. Before this cycle the same request produced a single arrival at the end.

**Evidence — the long reply is complete and untruncated:**

```
> 1 2 3 4 5 6 7 8 9 10 ... 55 56 57 58 59 60
```

Counted through to 60 with nothing missing, and the `> ` prompt sits before the reply rather than interleaved with it.

**Evidence — a stream cut mid-reply is not sold as complete:**

```
$ printf 'Count from 1 to 200...\n' | uv run axiom --host http://127.0.0.1:11435
axiom: qwen2.5:7b at http://127.0.0.1:11435
> 1 2 3
error: reply cut off after 6 characters - lost connection to http://127.0.0.1:11435
  ([WinError 10054] An existing connection was forcibly closed by the remote host)
>
```

A second proxy (`scratchpad/cut_proxy.py`) forwards to the real daemon and severs the connection 900 bytes into the response body. The fragment stays on screen — it was already printed, and hiding it would be a lie of a different kind — but it is immediately labelled, with the character count, and the partial reply does **not** enter history.

**Evidence — history still works under streaming:**

```
> Teal is splendid!
> Teal, remember?
```

## Criteria

| AC | State | Evidence |
|---|---|---|
| 1 prompt on start | met | transcripts |
| 2 documented defaults in `--help` | met | cycle 3 |
| 3 message → reply | met | transcripts above |
| 4 reply in full | **met — new** | count to 60 complete, prompt not interleaved |
| 5 progress while generating | **met — new** | 169 arrivals over 13s |
| 6 empty line does not call | met | cycle 2 |
| 7 multi-turn | met | regression above |
| 8 history sent | met | regression above |
| 9 in-process only | met | cycle 2 |
| 10 env var host / model | met | cycle 3 |
| 11 flag beats env beats default | met | cycle 3 |
| 12 effective host/model visible | met | cycle 3 |
| 13 unreachable host → named error | met | cycle 4 |
| 14 missing model → named error | met | cycle 4 |
| 15 partial output not sold as complete | **met — new** | cut-proxy transcript |
| 16 failed turn leaves session usable | met | cycle 4; prompt also returned after the cut above |
| 17 `/exit` → status 0 | met | cycle 2 |
| 18 EOF → status 0 | met | cycle 2 |
| 19 Ctrl-C semantics | **not met** | uncaught `KeyboardInterrupt` |

**18 met, 1 not met, 0 untested.** Was 15 / 2 / 2.

## Movement

Three criteria closed by one change — `stream=True` and printing pieces as they arrive. AC 4 and AC 15 had been untested since cycle 1 and are now settled with evidence rather than reasoning.

Note what closed AC 4: not the streaming itself, but finally asking for a reply long enough to truncate. Every earlier transcript asked for a short answer, which is why the criterion sat untested for four cycles instead of being wrongly marked met.

## Assumptions that changed

None.

## Goal check

**Not met.** 18 of 19. One remains: AC 19, Ctrl-C during generation cancels the reply and returns to the prompt; Ctrl-C at an idle prompt exits. Next action written.

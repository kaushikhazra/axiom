# Cycle 2 — 2026-08-24 00:37 IST

## Where the artifact stands

`src/axiom/__init__.py` is now 29 lines. The single exchange is a session: input loop, message list carried across turns, empty lines skipped, two ways out.

**Evidence — three turns in one process, third referring to the first:**

```
$ printf 'My favourite colour is teal. Reply in under five words.\nName one fruit, one word only.\nWhat colour did I say was my favourite?\n' | uv run axiom
> Teal is a beautiful color.
> Apple.
> Teal.
>
```

Turn 3 answers from turn 1's content, so history is genuinely being sent.

**Evidence — a fresh process starts empty:**

```
$ printf 'What colour did I say was my favourite? Answer in under ten words.\n' | uv run axiom
> You didn't say a favourite colour.
>
```

**Evidence — blank input does not reach the model:**

```
$ printf '\n\n   \n/exit\n' | uv run axiom
> > > >
```

Four prompts, no model output, returned immediately. Whitespace-only is skipped too.

**Evidence — exit statuses:** EOF on empty stdin exited 0. `/exit` exited 0. Both confirmed by the runner reporting success on the bare command.

## Criteria

| AC | State | Evidence |
|---|---|---|
| 1 prompt on start | met | `> ` in every transcript |
| 2 documented defaults, in `--help` | **not met** | still module constants; no `--help` |
| 3 message → reply | met | transcripts |
| 4 reply in full | **untested** | replies so far are one line by instruction; needs a long generation |
| 5 progress while generating | **not met** | nothing shown |
| 6 empty line does not call | **met — new** | blank-line transcript above |
| 7 multi-turn, process stays alive | **met — new** | three turns, one process |
| 8 history sent with each message | **met — new** | turn 3 recalled turn 1 |
| 9 state in-process only | **met — new** | fresh run denies the earlier colour |
| 10 env var host / model | **not met** | constants only |
| 11 flag beats env beats default | **not met** | no flags |
| 12 effective host/model visible | **not met** | not shown |
| 13 unreachable host → named error | **not met** | uncaught exception |
| 14 missing model → named error | **not met** | uncaught exception |
| 15 partial output not sold as complete | **untested** | no streaming, so no partial state |
| 16 failed turn leaves session usable | **not met** | any failure kills the process |
| 17 exit command → status 0 | **met — new** | `/exit` exits 0 |
| 18 EOF → status 0 | **met — new** | empty stdin exits 0 |
| 19 Ctrl-C semantics | **not met** | uncaught `KeyboardInterrupt` |

**8 met, 9 not met, 2 untested.** Was 2 / 14 / 3.

## Movement

Six criteria closed by one move: the `while` loop plus a message list. All six were blocked by the same missing thing, which is why cycle 1's action targeted it. No new code paths beyond the loop — 15 lines added.

## What is still missing, and is it closable

Nine not met, in three groups: configuration (2, 10, 11, 12), failure handling (13, 14, 16), and delivery (4, 5, 15, and 19 partly). All closable. Nothing found this cycle blocks anything.

## Assumptions that changed

None.

## Goal check

**Not met.** 8 of 19. Next action written.

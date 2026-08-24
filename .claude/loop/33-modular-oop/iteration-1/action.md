# Action

Build the seam. Cycle 2 established that config and context moved without a design decision
because neither touches the client, and that **nothing remaining has that property** -
`model_info_for`, `compact`, `compacted_history` and `maybe_compact` all take
`client: ollama.Client`, and `main()` catches three vendor error types by name. The seam is
not one of the four remaining extractions; it is what the other three are waiting on.

## Write `backend.py`

Three things, and resist adding a fourth:

- **A `ModelBackend` protocol** covering exactly what the program asks a model to do today:
  report the model's info, stream a chat turn, and produce a plain non-streamed reply for
  summarizing. Nothing speculative - AC 13 forbids an abstraction with one implementation and
  no test double, and the protocol only earns its place because the stub in the tests is the
  second implementation.
- **An `OllamaBackend`** implementing it, holding the `ollama.Client`, and the only place in
  `src/` that imports `ollama` or `httpx`.
- **Error translation at that boundary.** `ollama.ResponseError`, `ConnectionError` and
  `httpx.HTTPError` become this module's own error type or types, carrying whatever the
  caller needs to write the same message it writes today - including the host, since two of
  the three current messages name it.

The error taxonomy is the part to get right, because AC 10 depends on it. The three `except`
blocks in `main()` differ only in the message they print and whether a partial reply is
already on screen. Once they catch one family instead of three vendor types, they collapse
into one handler - that is the whole of AC 10, and it falls out of this design rather than
needing separate work.

Do not create `session.py` or `terminal.py` this cycle. One structural move per cycle, so a
transcript failure has one candidate cause.

## Then move compaction onto it

`compact`, `compacted_history` and `maybe_compact` into `compaction.py`, taking the backend
rather than a client. That closes AC 9 and it is the cheapest proof the seam is real: if
compaction can run against the stub with no vendor type in sight, the protocol is load-bearing
rather than decorative.

`main()` stays in `__init__.py` and keeps working. The entry point does not move.

## Watch for

**The transcript is the thing to protect.** Error translation is where behaviour drifts
silently - a reworded message, a lost `(status code: -1)` suffix, a missing leading newline
when a partial reply is already on screen. The baseline has all three failure messages
recorded verbatim. Run the characterization test after the backend lands and again after
compaction moves, not once at the end.

**The tests still patch `axiom.ollama.Client`.** They will keep working this cycle since
`__init__.py` still holds the client. Do not rewrite them onto the seam yet - that is AC 7's
own move and it deserves its own cycle. Note in the log whether the seam as built would in
fact let them stop patching globals, because if it would not, the protocol is wrong.

## Record

Full suite plus characterization after each of the two moves. `wc -l` across `src/` against
the 390-400 projection - this cycle is where that estimate gets its first real test. Status
token for all 20 criteria.

# Assumption

Standing inputs. These are given - do not re-derive them, and do not spend a cycle deciding
them.

## The codebase this lands in

#33, #34 and #35 all merged. `src/axiom/` is seven modules and 1246 lines; 179 tests.

- **`compaction.py` is where this lives.** `maybe_compact` triggers on the real running usage
  from the last completed turn; `compacted_history` replaces everything older than the kept
  window with one system summary; the ladder is `KEPT_PAIRS_LADDER = (10, 5, 2, 0)`.
- **A prior summary is carried forward verbatim.** `compacted_history` checks whether `older`
  begins with a system message and, if so, appends only newly summarized facts to it. **That
  is the growth #32 is about** - the summary is append-only today.
- **`_turn_boundary` snaps the cut to the next `user` message** (#34 cycle 6), because a turn
  that used tools is four messages, not two. Any change to the slicing must keep that.
- **`_as_line` renders tool calls into the summary transcript** (#34 cycle 6), which is what
  carries an address or a filename into a summary. #35 AC 26 depends on it.
- **`estimated_tokens` is a character count divided by four.** It is a proxy, used only to
  choose an escalation rung. #32 AC 3 asks for a check against the *real* assembled payload,
  and whether anything better than this estimate exists is an open question worth probing -
  Ollama's own tokenizer may or may not be reachable.
- **`terminal.py` owns every print.** AC 5's distinct message belongs there beside
  `note_compaction`.
- **`tests/conftest.py`** holds `StubBackend`, `feed()`, `chunk()`, `vendor_call()` and the
  autouse fixture clearing the three `AXIOM_*` variables.

## Given

- **`AXIOM_DEBUG_MAX_CONTEXT` is the tool for reaching the boundary quickly.** It replaces the
  computed context outright rather than capping it, which is why it can go below what the
  model and machine would allow. It is also still exported in this session's environment at
  500 - harmless for the suite, which isolates it, but visible in live runs.
- **Python 3.12, pytest, `uv`.** Dependencies now include `ollama`, `httpx`, `psutil`, `ddgs`
  and `trafilatura`. A new one needs a stated reason.
- **`axiom:main` stays the packaging entry point.**
- **The repo's own rules apply**: KISS over structure, one command per shell invocation,
  nothing committed under a `temp` name, loop files stay in this folder while code stays in
  `src/` and `tests/`.
- **The branch is `feature/32-compaction-overflow`.** Commits reference #32.

## Carried forward, worth not relearning

- **Probe before designing.** Every significant decision in #34 and #35 that was probed first
  held; both hypotheses reasoned from the code alone were wrong.
- **A scripted `.replace()` that does not match reports success.** It has happened four times
  across this queue. Verify scripted edits landed.
- **Test the world, not the message.** #34's timeout reported "stopped it" while the command
  kept running. Where a criterion is about what actually happened, assert on that.
- **A criterion can turn out to be wrong.** #35 AC 12 could not be met by asking a 7B model to
  be candid, and was replaced by axiom reporting what it had actually retrieved. Saying so
  with evidence is a result, not a failure.

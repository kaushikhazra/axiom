# Action

**Cycle 1 writes no production code.** The artifact already exists and is green; this cycle
records the baseline the behaviour criteria are later measured against, and probes the three
things that decide the shape of everything else.

## 1. Record the baseline

- `env AXIOM_HOST=http://127.0.0.1:1 AXIOM_MODEL=nonsense:99b AXIOM_DEBUG_MAX_CONTEXT=7 uv run pytest -q`
  Expect **317 passed**. Record the number; it is the floor.
- Copy the golden transcript aside: `tests/baseline/transcript.txt` to
  `.tmp/transcript-baseline-48.txt`. It **will** change this row, deliberately, and the copy
  is what makes "which lines changed" answerable later.
- `gh issue view 48` and record all 38 criteria as `not-started`.

## 2. Probe the three shape decisions

Against the local Ollama at `http://localhost:11434`. These are probes, not tests - nothing
here becomes a test that needs a live host.

- **What the client's listing call actually returns.** `ollama.Client(host).list()` - the
  object, not the HTTP JSON. Record the exact attribute path to a model's name, and whether
  it is `.name` or `.model`. The raw API carries both and they are equal here; the Python
  client may expose only one, and #43 lost a cycle to exactly this kind of assumption.
- **What it raises when the host is down, versus when the host is up and empty.** AC 31 and
  AC 32 are different messages with different exit codes, and they are only distinguishable
  if these two cases are distinguishable. Point at `http://127.0.0.1:1` for the first. Record
  the exception types. **If both look the same, say so** - that changes what AC 32 can claim.
- **How the process's exit status is actually set.** `main()` returns `None` today and
  `axiom:main` is a console entry point. Confirm what a returned value does versus
  `sys.exit(n)`, and record which one carries a status through `uv run axiom`.

## 3. Confirm the two facts the assumptions rest on

- **The list order is `modified_at` descending.** Already measured at scaffold time. Re-run
  `curl -s http://localhost:11434/api/tags` and confirm the order still matches what
  `assumption.md` records. If it has changed, that is itself the proof AC 6 needs.
- **`tests/conftest.py`'s `StubBackend`** - read it, and record what adding a fifth protocol
  method costs. Every existing stub must keep working.

## 4. Write cycle 2's action

Cycle 2 implements. Say in cycle 1's log which criteria it will take and in what order.
Suggested, because it is dependency order rather than difficulty order:

- The protocol method and the stub first - nothing else is testable without them.
- Then the settling logic as one decision function, with the list, the question and the
  refusals in `terminal.py`.
- Then the remembered choice, which is a second file and can be built once the settling
  logic has somewhere to ask.
- The transcript regeneration last, once the startup line has stopped moving.

## Record

Status for all 38 criteria. The three probe answers, verbatim. The baseline test count. Any
assumption that changed.

**Write no questions into anything.** Decide, record the decision and the reasoning under a
heading that says so, carry on. The one exception is safety, not uncertainty.

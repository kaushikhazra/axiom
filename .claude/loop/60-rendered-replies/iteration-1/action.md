# Action

**Cycle 1 reads the prior art, adds the dependency, and probes the streaming problem. No
production rendering yet.** The three references all solve the same problem and there is no
reason to rediscover it.

## 1. Baseline

- `env AXIOM_HOST=http://127.0.0.1:1 AXIOM_MODEL=nonsense:99b AXIOM_DEBUG_MAX_CONTEXT=7 uv run pytest -q`
  Expect **539 passed**. Record it.
- Copy `tests/baseline/transcript.txt` to `.tmp/transcript-baseline-60.txt`. **It should not
  change this row** - check it every cycle.
- `gh issue view 60`, record all 29 criteria `not-started`.

## 2. Read the prior art before writing anything

`md2term`, `richify`, and the `simonw/llm` PR. **Fetch and read them.** Each solves streaming
markdown; the question to answer for each is *how does it avoid redrawing what is already on
screen*, because that is AC 7 and it is the whole difficulty.

Record what each does, in one line each, and which approach this row will take and why.

## 3. Prove the naive approach is wrong, rather than assuming it

Write a throwaway script in `.tmp/` that streams a long markdown reply through
`rich.Live(Markdown(...))`, capturing the byte stream. **Count how many times a given line is
emitted.** If it is more than once, that is AC 7's justification recorded as a measurement rather
than an assertion - and if it is not, the assumption is wrong and this row is easier than
thought.

## 4. Add the dependency

`rich` in `pyproject.toml`, pinned. Record the version. `uv sync`, then the full suite again -
**adding a dependency must not move a single test.**

## 5. Probe the hard case

The tension between AC 8 and AC 9, with a real streamed reply from the local Ollama containing a
fenced code block. Capture the chunk boundaries: how much of a fence arrives per chunk, and what
a renderer would have to hold. Record the real chunk sizes rather than guessing them.

## 6. Write cycle 2's action

Cycle 2 implements. Say which criteria it takes and in what order. The seam is `show_piece` and
`end_reply` in `terminal.py`; nothing above them should need to change, and if it does, say why.

## Record

Status for all 29. What each reference does. The naive-redraw measurement. The pinned version.
The real chunk sizes. Whether the transcript moved.

**Write no questions into anything.** Decide, record the decision and the reasoning under a
heading that says so, carry on. The exception is safety, not uncertainty.

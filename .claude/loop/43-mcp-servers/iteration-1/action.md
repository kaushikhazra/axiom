# Action

**Cycle 1 writes no production code.** Record the baseline, install the dependency, and probe
the two things that decide the shape of everything else. This is the largest issue in the
queue; a wrong structural guess here costs more cycles than measuring does.

## 1. Record the baseline

- Full suite and the hermeticity check. Confirm 272 green.
- Copy `tests/baseline/transcript.txt` to `.tmp/transcript-baseline-43.txt`. **AC 29 is
  measured by this file.**
- Record today's startup line exactly, for a default run and for `--no-tools`. AC 1 and AC 29
  are about it not moving.

## 2. Add `mcp` and find out what it actually gives you

`uv add mcp`. Then a script in `.tmp/`, not a test - measure rather than trust the notes in
`assumption.md`:

- Build a tiny in-memory server with two tools and connect a `Client` to it.
- **What does `list_tools()` actually return?** Print one tool object whole: the exact
  attribute names, and the exact shape of `input_schema`.
- **Does that schema drop straight into an Ollama declaration?** `declarations()` emits
  `{"type": "function", "function": {"name", "description", "parameters"}}`. Try it. If the
  schema needs adjusting, find out now, not in cycle 4.
- **What does `call_tool` return for a success and for a failure?** Print `.content`,
  `.is_error` and `.structured_content` for both. `tools.run()` returns a plain string, so
  something has to turn content blocks into one - decide what happens to a non-text block.
- **What version of `mcp` actually installed**, and does it match the v2 API in
  `assumption.md`? If the API differs, that is the most important finding in the cycle.

## 3. Probe the sync/async bridge

The SDK is async-only and axiom is entirely synchronous. `assumption.md` says a background
event-loop thread; **measure that it works before building on it**:

- Start a loop in a daemon thread, open a `Client` inside it, and call a tool from the main
  thread with `asyncio.run_coroutine_threadsafe(...).result()`.
- Does the session stay usable across several calls?
- What happens on shutdown - does the loop thread stop cleanly, and does the client's context
  manager exit properly from another thread?
- Time one call. If the bridge adds meaningful latency per call, say so.

## 4. Probe the thing AC 26 and AC 27 rest on

Write a trivial stdio server as a script under `.tmp/` for now, start it through the SDK, and
find out:

- What is the child process's pid, from axiom's side?
- After the client's context manager exits, is the process actually gone? Check with
  `psutil`, not by assuming.
- **What happens if the parent is killed without exiting cleanly?** That is AC 27, and it is
  the one most likely to be false by default.

Non-destructive throughout, and the script is ours - `CLAUDE.md`'s clause forbids fetching a
server for a test, and that applies to probes too.

## 5. Say what the fix will be

One paragraph per group of criteria, no code. Where the config is read, how `REGISTRY` stops
being import-time static, where the event loop lives, how a prefixed tool routes back to its
server, and what `to_send`/`declarations` look like when tools come from two places. If a
probe shows the obvious approach is wrong, say that instead.

## Record

Status for all 30 - most will read `not-started`, which is correct for this cycle. Then write
cycle 2's `action.md`.

**Write no questions into it.** Decide, record the decision and the reasoning in the log,
carry on. Nobody is reading between firings.

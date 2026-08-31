# Action

**Start AC 15 and AC 16. They are the long pole and everything else can wait.**

Twelve criteria remain and eleven of them are ordinary. These two are not: they need real
models, real latency and repeated runs, and they cannot be stubbed, asserted or reasoned
into place. The fail-safe is 21:30. Left any later they will be settled from one lucky run,
which is exactly what AC 16 exists to forbid.

**AC 15** - asked for something a loaded skill covers, the model invokes it rather than
answering from memory, evidenced by repeated runs against each installed model, counts
recorded.
**AC 16** - where a model cannot do that reliably, the numbers are recorded rather than
rounded up.

Do this:

1. **`ollama list`** - find out what is actually installed. Record the list in the log; it
   is part of the evidence.
2. **Build the lane.** Live-model tests do not run in the hermetic suite - that has been an
   assumption since cycle 1 and nothing has enforced it yet. A pytest marker, deselected by
   default in `pyproject.toml`, is enough. **Prove the default run does not include them**
   before writing the measurement, or the suite silently acquires a network dependency.
3. **One skill, one question, N runs per model.** The skill should cover something the model
   would otherwise answer from memory - that contrast is the measurement. Count invocations
   out of N. Ten runs per model is the minimum that can distinguish "usually" from "once".
4. **Record every model's number, including the bad ones.** A model that scores 3/10 is AC
   16's case and the criterion is met by writing 3/10 down, not by tuning until it improves.

**The preamble is the only lever, and cycle 2 forbade shortening it on taste.** If a model
scores badly, that is the moment the wording becomes an empirical question - change it,
re-measure both models, and keep the change only if it improves one and worsens none. That
is #68's rule and it applies here for the same reason.

**Working directory: `C:/Projects/.tmp/axiom-tool-sandbox`.** CLAUDE.md's rule holds - a
live model is asked only for non-destructive work, and a skill it might invoke must not tell
it to do anything else. Write the skill the test uses; do not let a model improvise one.

Leave AC 25, 29, 31, 32, 34, 35, 40, 43 and 44 alone this cycle. They are cheap and they
will still be cheap at 20:00.

First thing to tackle: **`ollama list`, then the marker and the proof it is deselected** -
because a live test that accidentally joins the default suite makes every later cycle's
wall-clock measurement meaningless.

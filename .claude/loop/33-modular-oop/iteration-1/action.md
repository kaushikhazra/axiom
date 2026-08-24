# Action

Cycle 1 left one thing unproven and one thing undone. Do them in that order - the second is
not trustworthy until the first is settled.

## First: prove the instrument detects a change

`tests/baseline/transcript.txt` has only ever passed. A golden master that has never failed
is not yet known to catch anything, and every later claim about AC 1 rests on it.

Make one deliberate, trivial change to an observable string in `src/axiom/__init__.py` - a
single character in the startup line is enough. Run the characterization test. It must fail,
and the failure must name the scenario that changed. **Then revert the change** and confirm
the suite is green again at 25/25.

Record both outcomes in the log. If it does not fail, the instrument is broken and fixing it
is the whole of cycle 2 - do not proceed to the extraction on an instrument that cannot see.

## Then: extract the two clusters that have no seam question

Take `config.py` and `context.py` out of `src/axiom/__init__.py`, in that order, using the
shape named in cycle 1.

- `config.py` - `DEFAULT_HOST`, `DEFAULT_MODEL`, `parse_args`, and the resolution of
  `AXIOM_HOST`, `AXIOM_MODEL` and `AXIOM_DEBUG_MAX_CONTEXT` into one settings object.
- `context.py` - `model_max_context`, `kv_cache_bytes_per_token`, `available_memory`,
  `memory_safe_context`, `_find`, and the constants they use.

These two first precisely because they raise no question about where the backend seam sits.
They are close to pure functions over data, they move without a design decision, and moving
them exercises the whole apparatus - transcript, suite, line count - on the lowest-risk
change available. If something about the method is wrong, it is far cheaper to find out here
than inside the seam.

Leave `model_info_for` where it is for now: it calls the client, so it belongs to the
backend question, not this one.

`main()` stays in `__init__.py` and keeps working. The entry point does not move (AC 3).

## Record

Run the full suite and the characterization test after each extraction, not once at the end -
if the transcript changes, the smaller the step that caused it, the shorter the search.

Report `wc -l` across all of `src/` against the 447 ceiling, since two files now exist where
one did, and this is the first real evidence of whether AC 14 is comfortable or tight.

Give all 20 criteria a status token. AC 1 moves only if the transcript still matches after
the extraction; AC 4 and AC 14 are the two that should show real movement this cycle.

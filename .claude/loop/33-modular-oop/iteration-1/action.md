# Action

Close AC 5 and AC 4 without breaching AC 14. Cycle 3 left 20 lines of headroom and the
terminal still unsplit, so this cycle is a squeeze, not an expansion. Do the two routes in
order - the reclaim first, because it buys the room the split needs.

## First: reclaim lines that carry no knowledge

Before adding a module, take back what is being spent on docstrings that restate their own
signature. Candidates identified in cycle 3:

- `ModelBackend` - six lines of docstring for three signatures.
- `Piece` - a docstring for a two-field frozen dataclass.
- `Settings` - check whether the debug-override note is still earning its length.
- `OllamaBackend.complete` and `.model_info` - one-line docstrings restating the name.

**Do not touch these.** They are earned findings and losing them costs more than the lines
are worth: the KV-cache derivation in `context.py`, the never-re-summarize rationale in
`compacted_history`, the leading-blank-line explanation in `report_failure`, the
`estimated_tokens` note about why it is an estimate at all, and the module docstring in
`backend.py` explaining why the seam exists.

Record `wc -l` before and after this step alone, so the reclaim is measured rather than
assumed.

## Then: one module, not two

Create `terminal.py` and move every `print` and the `input` call into it - the startup line,
the prompt, the streamed reply, the compaction notice, and `report_failure`.

**Leave the chat loop in `__init__.py`.** Nothing in #33 requires a separate `session.py`.
AC 5 is satisfied when `__init__.py` stops writing to the terminal itself and calls the
terminal module instead; AC 8 only asks that whichever module holds the loop names no vendor
client, and `__init__.py` already names none. A third module would cost 15-20 lines to satisfy
a criterion nobody wrote.

That is a KISS decision under AC 12 and AC 13, not a shortcut - say so in the log, and say
what would change the answer.

## Watch for

**The startup line is assembled from three parts** - model, host, and a context note that
depends on whether a debug override is in play. Decide deliberately whether the terminal
formats it from settings plus a context value, or receives a finished string. The first keeps
formatting in the terminal where AC 4 wants it; the second leaves formatting in the loop.
Prefer the first.

**The transcript is the whole safety net for this move.** Every one of the thirteen scenarios
exercises printing. Run the characterization test immediately after the move, before anything
else.

## Record

`wc -l` across `src/` after the reclaim and again after the split, both against 447. If the
split lands over the ceiling, do not delete knowledge-bearing comments to squeeze under it -
report AC 14 unmet, with the exact overage and what it would cost to close.

Status token for all 20. AC 4, AC 5 and AC 14 are the three that should resolve this cycle,
and AC 7's remaining half - letting `main()` take a backend from its caller - is the natural
next move once the terminal is out.

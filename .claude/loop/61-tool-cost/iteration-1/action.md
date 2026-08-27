# Action

**Cycle 1 records the baseline, reproduces the invisibility, fixes it, and covers the twelve.**

## 1. Baseline

- `env AXIOM_HOST=http://127.0.0.1:1 AXIOM_MODEL=nonsense:99b AXIOM_DEBUG_MAX_CONTEXT=7 uv run pytest -q`
  Expect **505 passed**. Record it.
- Copy `tests/baseline/transcript.txt` to `.tmp/transcript-baseline-61.txt`.
- `gh issue view 61`, record all 12 criteria `not-started`.

## 2. Reproduce it, before touching src

A run with tools and **no MCP server**: today no cost line appears at all. Watch it fail.

Then a second failing test: the figure must include the standing prompt. Today the sum passed to
`note_servers` covers only the declarations, so even the MCP case understates it.

## 3. Fix

Move the cost out of `note_servers` into its own saying, printed whenever tools are available.
`note_servers` keeps the per-server counts, the bounds and the problems.

Include the standing prompt in the sum, and take the figure from
`compaction.estimated_tokens` over the same payload the size checks weigh.

**Decide and record**: where the line sits relative to the startup line and the server lines, and
why. It is a fact about the session, so it belongs with the session's other facts.

## 4. Cover the twelve

- **AC 1, AC 2, AC 4** - a run with tools and no server says the cost, against the window, once,
  at startup.
- **AC 3** - the figure covers built-ins, server tools **and** the standing prompt. Assert it
  equals `estimated_tokens` over all three, computed in the test.
- **AC 5, AC 6** - `--no-tools` and a model that cannot call them are both silent. **Pair each
  with a positive**, or "said nothing" passes for an implementation that never speaks.
- **AC 7, AC 8** - `--no-web` reports the cost of what is *actually* declared, and the figure
  falls relative to web-on. Two settings, compared to each other.
- **AC 9** - asserted against `compaction.estimated_tokens`, never a constant.
- **AC 10** - after a switch, the figure belongs to the new model's tools. Two models, different
  tool support.
- **AC 11, AC 12** - the transcript, and the existing MCP tests, are the evidence.

## 5. The transcript

It **will** change - a line appears in every scenario that has tools. Fix every stub first,
regenerate deliberately, read the whole diff, `grep -c "^<"`. Account for every changed line.

## 6. Then

Full suite and the hermeticity command. Break the fix, record how many go red **and name every
survivor with a verdict**. Write cycle 2's action: a cold read of all 12 from GitHub, before the
diff and before this log.

## Record

Status for all 12. The failing-test-first evidence. The placement decision. The break count and
survivors. Every transcript line that changed and why.

**Write no questions into anything.** Decide, record the decision and the reasoning under a
heading that says so, carry on. The exception is safety, not uncertainty.

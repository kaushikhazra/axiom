# Action — cycle 5

Stage 3, second half: **the voice, the tool summary and the prompt.**
AC 22 to 30, and the guards 32, 35, 36, 37.

Thirteen criteria left. This is the last block of new behaviour.

## Read first

- `.tmp/mock_quiet_turn.py` — variant **D** is the agreed design: nothing per
  call, one grey line after the turn, `·  4 tools, 2 failed`.
- `.tmp/mock_turn.py` — the greys and the one-line forms.
- `logs/cycle-4.md` — the terminal-only split is the shape to reuse. Anything that
  changes what a redirected run prints will move the baseline, and the baseline
  has not moved once in four cycles.

## Do these in order

1. **The tool summary.** `note_tool` currently prints a line per call plus an
   `outside the working directory` line. On a terminal: nothing per call, a
   transient progress line while one runs, and one grey summary after the turn.
   Not at a terminal: **unchanged**, or the baseline moves — it holds seven
   `axiom: read_file(...)` lines and they are the transcript's record of #34.

2. **The voice in grey**, `terminal.VOICE_GREY`, and the `axiom:` prefix dropped
   in favour of `·` — AC 27, AC 28. Terminal-only again. `VOICE` stays for the
   plain path.

3. **The prompt** — AC 30. A single `>` in the accent, the typed line at the
   terminal's own foreground.

## The two that will be got wrong

- **AC 22 and AC 26 — nothing per call remains on screen.** The failure mode is a
  transient line written and never erased: fine in a fast test, a trail of
  spinners in a real terminal. **Assert on what is on the screen at the end**,
  through `tests/screen.py`, not on what was written. A test that greps the byte
  stream for absence will pass on output that is still sitting there.

- **AC 35 — a bare run says no more than before.** A redesign is when a quiet path
  grows chatty. Compare a no-tools, no-servers, no-skills run against the
  baseline's own bare-run sections, and count lines rather than reading them.

## Also

- AC 23 needs the user to see *something* while a tool runs. A test cannot watch
  a spinner; assert that something is written before the tool returns, with a
  stub tool that blocks until released.
- AC 25 — a turn calling no tools shows no summary line — is the boundary that
  makes AC 24 mean anything. Both, or neither counts.
- AC 36's second half is "counted in the summary line", which needs a turn with
  one failing and one succeeding call.

## Do not

- Regenerate the baseline. Four cycles, zero lines. If it moves, the terminal-only
  split has been broken somewhere.

## Record

`logs/cycle-5.md`, per `observe.md`. If all 37 land, say so and stop the loop:
delete the cron, and say that too.

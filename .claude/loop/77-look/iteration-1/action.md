# Action — cycle 4

Stage 3, first half: **the session's facts as a panel, and the clear before it.**
AC 7 to 16.

This is the expensive stage. Split it: the panel and the clear this cycle, then
the voice, the tool summary and the prompt in cycle 5. Doing all of AC 7 to 33 in
one pass puts the whole 78-line baseline diff behind a single green light.

## Read first

- `.tmp/mock_startup.py` — the agreed design. `--static` draws all eight states.
- `logs/cycle-3.md` — three of six tests were hollow last cycle and the reasons
  generalise: a break that does not violate the criterion; a boundary that is not
  at the boundary; a check that reads correct behaviour as failure.

## Do these in order

1. **The info panel** replacing `note_settled`, `announce`, `note_tool_cost`,
   `note_servers` and `note_skills`. A row exists only where today's code prints
   a line — that is AC 12 and it is what keeps a bare run bare.

2. **`console.clear(home=True)` when the model is settled**, before the panel.
   AC 7, and AC 10 says once and never again. Prove AC 10 by running a session
   with several turns and counting the clears, not by reading the call site.

3. **AC 9 — scrollback survives.** `clear(home=True)` does not touch it. Assert
   on the escape actually emitted rather than on Rich's promise: a clear that
   sends `\x1b[3J` wipes scrollback and looks identical in every other way.

4. **The failures outside the box** — AC 16. They go to stderr today; keep them
   there and keep them visibly not part of the facts.

## The baseline

**78 of 477 lines change here.** Read the diff, line by line, and summarise it in
the log. `AXIOM_WRITE_BASELINE=1` exists; using it to clear a red is the one thing
that defeats the file.

Before regenerating, ask the question #75 asked and got right: **can the code be
narrowed so the baseline is restored rather than updated?** The transcript captures
a non-tty run, and a non-tty run has no reason to draw a box. If the panel is drawn
only at a terminal — which the chooser already does, `force_terminal=sys.stdout.isatty()`
— then **the baseline may not need to change at all**, and 78 lines of diff become
zero. Check that before anything else. It also decides AC 33.

## Watch for

- **AC 12 will pass vacuously.** "A fact axiom does not have is left out" is true
  of a panel that leaves out everything. Assert both directions: absent when
  unknown, present when known.
- **AC 15** — the settle reason on the model's row — is the one criterion in this
  group that is not already true in some form. Do not let it ride on AC 11's test.
- **The four negatives** in `test_models.py` and `test_switch.py` still lean on the
  phrase `models on`. Stage 3 does not touch the chooser, so they should be
  untouched; if one changes, something reached further than intended.

## Do not

- Touch the voice, the tool summary or the prompt. Cycle 5.
- Regenerate the baseline to clear a failure.

## Record

`logs/cycle-4.md`, per `observe.md`. Criteria met out of 37, the suite count and
wall-clock, and the baseline's state — untouched, or the diff summarised.

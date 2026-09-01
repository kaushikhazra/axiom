# Action — cycle 6

**Three criteria left: 27, 28, 29 — the voice.** If they land, the loop is done.

## The change

`terminal.py` says everything in its own voice through 44 f-strings of the form
`print(f"{VOICE} ...")`, seven of them with `file=sys.stderr`. AC 27 wants all of
it drawn dimmer than the model's answer; AC 28 wants none of it beginning with
axiom's own name.

Add one `say(message, stream=None)` and convert the call sites:

- **at a terminal, with rendering on** — `·  <message>` in `VOICE_GREY`
- **anywhere else** — `axiom: <message>`, exactly as today

`_grey` already exists from cycle 5. The gate is `_rendering and <stream>.isatty()`,
the same pair every other path added by #77 uses. Gate on the **stream being
written to**, not on stdout, or a stderr line takes stdout's answer.

## Do it mechanically, then read the diff

Forty-four sites is a scripted replace, and this repo has a rule about those:
**anything containing a backslash escape goes through the Edit tool.** Check the
list for multi-line `print(...)` calls before running anything - a regex that
handles the single-line form and silently skips four others leaves four lines
still saying `axiom:`, and AC 28 is a claim about **every** line.

Count before and after: `grep -c 'f"{VOICE}' src/axiom/terminal.py` should end at
the number `say` itself uses, and no more.

## Prove

- **AC 28 is the one that will pass hollow.** "No line begins with its own name"
  is easy to check on one line and the criterion is about all of them. Drive a
  session that exercises many voice lines - a missing model, a forgotten choice, a
  server that fails, a skill that will not load - and assert **no line on the
  screen** starts with `axiom:`.
- **AC 27** needs the comparison, not just the colour: axiom's lines carry the grey
  and the model's answer does not.
- **AC 29** - a failure drawn differently from both - needs three things on screen
  at once: an answer, an ordinary voice line, and a failure.

## Do not

- Change what the plain path says. The baseline has not moved in five cycles and
  `say` is the one function that could move all 78 lines at once.

## If all 37 land

Say so, and **stop the loop**: delete the cron, and record in `logs/cycle-6.md`
that it was deleted. Then say what is left for a person - the manual pass over
#72, #73 and #74 that was paused for this work, and the fact that #77's own
behaviour has been proved by tests but not yet driven by hand.

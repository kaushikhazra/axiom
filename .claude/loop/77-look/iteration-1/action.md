# Action — cycle 2

Stage 1 of the build order: **the reply's palette, and the unlexed fence.** AC 17 to 21.

Cycle 1 found the guard for AC 31 is blind to the colour being added, so that is fixed
*first* — a palette landing behind a guard that cannot see it is how a wrong hue ships
looking covered.

## Do these in order

1. **Widen the NO_COLOR guard before adding any colour.**
   `test_rendering.py:679` searches `\x1b\[[0-9;]*3[0-7]m`, which catches 16-colour and
   misses both `38;2;r;g;b` and `38;5;n`. Widen it, then **prove the widening** by
   asserting it catches all three forms directly — a regex fix nobody watched work is the
   same hole one layer down.

2. **Add the accent as a module-level constant in `terminal.py`,** with the voice grey
   beside it. Values are in `assumption.md`; do not re-derive them.

3. **Add a module-level Rich `Theme`** and reference it inside `_as_markdown`'s Console.
   No signature change — cycle 1 established the seam. The full style map is in
   `.tmp/mock_reply.py` as `LOUD`; copy it rather than reinventing it, including the two
   comments explaining why `markdown.code_block` and `_highlighted` are left alone.

4. **Make the unlexed fence plain.** terminal.py:918 becomes `return line`.
   Then **delete `_colourless()`** — cycle 1 confirmed it has no other caller.

5. **Settle the recorded decision this deletes.** `NO_COLOR=` with nothing after it counts,
   and that opinion lived only in `_colourless()` and the test at line 718. Either write a
   test that asserts the presence-semantics against Rich directly, or state in the commit
   that axiom defers to the renderer. **Do not let it lapse silently.**

6. **Re-point the cyan assertions** at test_rendering.py 287, 328, 693, 701, 718. Three of
   them go vacuous rather than red — 693, 718 and 287 — so they must be rewritten, not
   deleted and not left passing. 701 and 328 will fail honestly.

## Prove, do not claim

For each of AC 17, 18, 19, 20, 21 and 31: **break it and watch the test go red.** Narrow
breaks - cycle 1's own reading found three separate loops that lost a criterion to a break
too wide to attribute.

AC 34 gets its guard here too, since this is the cycle that could violate it: render a
reply through `Rendered` before and after, compare the screen text, and **normalise Rich's
OSC-8 link ids first** or a reply containing a link compares unequal to itself. That gap
is in `tests/screen.py` and is described in `assumption.md`.

## Do not

- Touch the chooser or the info panel. That is stages 2 and 3.
- Touch `tests/baseline/transcript.txt`. Stage 1 cannot reach it — rendering is gated on
  `isatty` and the transcript captures a non-tty. **If the baseline moves this cycle,
  something is wrong and that is the finding.**

## Record

`logs/cycle-2.md`, per `observe.md`. Criteria met out of 37, the suite count and
wall-clock, and whether the baseline is untouched.

# Action

Seven of thirteen criteria are met with tests that go red when the fix is removed. The four
untested ones are all the same shape: they are about the **full output path**, not the
renderer, and none can be settled by feeding `Rendered` a string.

1. **AC 11 and AC 12 — `--no-render` and piped output, byte for byte.** Run the same nested
   reply with rendering on and off and compare. The bar is byte-identical to what the same
   reply produced before this issue's change, which means capturing it from `git stash` or
   from the merge base rather than trusting that nothing moved.
2. **AC 13 — the indent structure on screen matches `--no-render`'s.** Not the bytes: the
   *structure*. Parse both into (depth, marker) and compare the shapes. This is the
   criterion that would catch the depth stack disagreeing with the markdown the model
   actually wrote.
3. **AC 9 — a list nested deeper than the window is wide.** Measure before deciding what to
   do: a nested item now passes only its text to `_as_markdown`, with no marker, so it takes
   the paragraph branch and may already keep every character. If it does, say so with a test
   and move on. **If it does not, stop** - that is #72's crop, #72's loop owns it, and
   fixing it here would put two half-fixes in one function.
4. **Break each new test.** Three of eleven written last cycle were vacuous and only the
   break found them. Assume the same rate again.
5. `uv run pytest` - 630 on this branch, and it stays green.

Do not touch `_as_markdown`'s `soft_wrap`. Loop 72 is changing that function this hour and
the two changes must not collide.

First thing to tackle: **AC 13, the structural comparison against `--no-render`.** It is the
only one of the four that can find a *wrong* answer rather than a missing one - the others
confirm nothing was lost, this one confirms the depth stack agrees with the source.

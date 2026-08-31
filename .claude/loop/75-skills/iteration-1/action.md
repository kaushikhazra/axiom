# Action

Two things, in this order.

**First, run the break cycle 1 did not.** AC 33 — instructions read at invocation rather
than at load. Add a `body` field to `Skill`, populate it in `_one`, return it from
`instructions()`, and watch `test_instructions_are_read_at_invocation_not_at_load` go red.
Then revert and re-establish green before touching anything else. It is one criterion, but
it is the one observe.md flags as most likely to be quietly false, and cycle 1 reasoned
about it instead of proving it. While the breaks are cheap, run them for AC 28 and AC 41
too and move those three out of the second bucket.

**Then fix the shape of the cost.** Cycle 1 measured the catalogue: a 302-character
preamble that costs about 75 tokens, plus 88 characters per skill. The first skill
therefore costs 97 tokens of which 22 is the skill. **The explanation outweighs the
content until there are four skills**, and every user with one skill pays for a paragraph
about skills in general.

Get the preamble down. The standing prompt already tells the model what it is and what its
limits are; the catalogue does not need to re-explain the concept from scratch. Aim for a
line, not a paragraph, and **re-measure** — the table in cycle 1's log is the baseline and
the next log must show the same four rows.

Do not start the four tools or the two commands yet. Both read from the catalogue, and the
catalogue's shape is still moving.

First thing to tackle: **the AC 33 break** — because everything after it is built on the
claim that instructions live on disk until they are wanted, and that claim has not yet been
tested by removing it.

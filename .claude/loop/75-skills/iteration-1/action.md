# Action

**First, declare only the skill tools that can do anything.** Cycle 3 measured four skill
tools costing 396 tokens on every request with no skills configured - the tool count went
10 to 14 and the cost 1111 to 1507, which is 87% above `master` before #74. AC 1 says a run
with no skills starts as it does today, and paying 36% more for four unusable tools is not
that.

`read_skill`, `delete_skill` and `invoke_skill` do nothing against an empty catalogue and
should not be declared when it is empty. `write_skill` is always declared, because writing
the first skill is how a catalogue stops being empty. The seam is `_prepare` in
`src/axiom/__init__.py`, which already drops `WEB_TOOLS` when `--no-web` is set - follow
that, and use `SKILL_TOOLS`, which exists for this.

The declarations have to be rebuilt when the first skill is written, or a session that
starts empty can never invoke what it just created. That is the same restatement
`restate_skills` already does for the prompt, and it is the thing this change is most
likely to get wrong. **Test it as a sequence: start empty, write, then invoke.**

Re-measure the table in cycle 3's log and put the new numbers beside it. Regenerate the
golden baseline afterwards and **read its diff** - if anything other than the tool count and
the cost has moved, that is a defect, not a baseline update.

**Then run the two breaks cycle 3 could not count.**

- **AC 42** - move validation to *after* the file is opened for writing, so a refused write
  truncates the good skill. The test must go red for *that*, not because its setup stopped
  working.
- **AC 22** - make a tool-written skill differ from a hand-written one.

Cycle 3 turned both red with a break that hit their setup instead of their claim, and did
not count them. Do not count them until a break lands on the criterion itself.

Leave `/skill` and `/skills` for the cycle after, still. The REPL is a different seam and
the declaration change above touches the same function that decides what a model is offered.

First thing to tackle: **the conditional declarations**, because the cost is a promise the
issue makes in AC 1 and every later cycle measures against a number that is currently wrong.

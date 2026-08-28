# Action

Cycle 2 built the seam and stopped before wiring it, because building it surfaced a question
reading could not: **the prompt travels with the read.** The thread prints `> ` and blocks,
so a job firing now would draw its turn underneath a prompt that is still live. Decide that
before touching `_chat`, or the mess goes into the main loop and AC 13 gets harder rather
than easier.

1. **Decide how the prompt is drawn, by measuring rather than preferring.** Cycle 2 listed
   three options. Write the smallest possible harness that renders each against a modelled
   screen - `tests/screen.py` already models one for #60 - and look at what a user would
   actually see when a job fires mid-wait. Pick from that.
2. **Then wire the dispatch into `_chat`**, at the top of the loop, where a due job's prompt
   takes the place of a typed line and goes through the same path. One turn is one pass of
   that loop; do not add a second turn-execution path, or AC 10 and AC 11 stop being free.
3. **Mark a scheduled turn as axiom's own voice** (AC 13). `VOICE` is how axiom's lines stay
   apart from the model's, and #60 AC 17 and AC 29 both bind here - a scheduled turn does not
   get a fourth voice, it gets axiom's.
4. **Prove the three that will be got wrong**, from `observe.md`: a due job runs while the
   user types nothing; a job due mid-turn runs *after* the turn; two jobs due at once run in
   order. Controlled clock, fake stdin, nothing sleeps.
5. **Break each of those three.** Loop 73's cycle 2 found three of eleven of its own tests
   vacuous, and only the break found them. Assume this cycle's are no better until shown.
6. `uv run pytest` - 654 on this branch, green, and the wall-clock time must not climb.

Leave the three tools, listing, announcing, expiry and AC 27 alone. Nothing can fire until
step 2 lands, and tools that schedule work nothing can fire are decoration.

First thing to tackle: **what the user sees when a job fires while they are sitting at the
prompt.** It is the only open question, every remaining criterion is drawn on top of it, and
it cannot be answered by reading the code - cycle 2 tried.

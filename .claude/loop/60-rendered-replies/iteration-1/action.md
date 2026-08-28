# Action

**A third read, narrowed to what cycle 5 touched.** Not a re-read of the row.

The trend is the reason: cycle 4 found four defects in cycle 3's code, cycle 5 found three
in cycle 4's. Every fix is new code, and new code is where the defects are. Cycle 5's three
fixes have had no hostile reader.

**The stopping rule is external, and it is this:** a read that finds nothing takes exit 1
and closes the queue. A read that finds something fixes it and writes another action. The
fail-safe at **07:07 IST** ends it either way. Do not substitute a judgement that the work
looks finished.

## 1. Check the ground

- Full suite. **614 is the floor.**
- `env AXIOM_HOST=http://127.0.0.1:1 AXIOM_MODEL=nonsense:99b AXIOM_DEBUG_MAX_CONTEXT=7 uv run pytest -q`
- Golden transcript **unchanged**.
- `python .tmp/break60.py` — 28 breaks. **Read every line of its output**, not just the
  survivor count: three breaks were found stale in cycle 5, silently proving nothing while
  the run reported no survivors. Five have now been found to be no-ops across this row.

## 2. Attack cycle 5's three fixes

**`_echo_limit`** holds one character back when the echo would land on a multiple of the
width. What if the line is exactly one character long and the width is 1? What if a wide
character means the echo *jumps over* the boundary rather than landing on it - 39 columns
used, next character two cells wide, at width 40? Nothing lands on 40 and the terminal wraps
anyway. Check it.

**`_echo_width`** is remembered when text is echoed and used when it is taken back. It is
reset when a line commits and in `finish`. Is there a path where a line is echoed, the width
is remembered, and then a *different* line is committed against it - the table hold, where
`_finished` erases without committing? Follow the held-row path specifically.

**`_is_a_rule`** requires a line to be nothing but rule characters and spaces. What draws
such a line other than a table? A model writing a horizontal rule `---` inside a table
block; a row whose only cell content is a dash. Try a table whose *data* row is
`| --- | --- |` repeated, and a reply that is only ` ─── ` inside pipes.

## 3. Attack the harness

Five of its breaks have been no-ops. Add a guard rather than finding a sixth by luck: make
`.tmp/break60.py` **fail loudly** when a break's target does not match, and when a break
produces no failures - a break that changes the file and breaks nothing is either a no-op or
an untested behaviour, and both are worth stopping for. Then run it.

## 4. Then

If it finds something: fix it with a test that fails first, add its break, write cycle 7's
action, commit, push, exit.

If it comes back clean, that is **exit 1**:

- all 29 met, suite green and hermetic, transcript unchanged, a real before-and-after
  recorded across the cycle logs
- commit, push, open a PR referencing #60, **merge it**, delete the branch
- then, in the same run: mark row 16 done in `queue.md` with the PR number, the cycle count
  and the wall-clock time, **say the queue is empty**, and update `../../handoff.md` -
  manual testing is still unfinished, #41, #34, #40, #35 and #26 were never reached, and
  seven rows have merged since it was last written
- **do not touch the cron.** With the queue empty there is no next row to redirect it to;
  say so in the handover and leave it for Kaushik to stop

## 5. Say how cold it was

Cycles 4 and 5 were read by the same session that wrote the code, with no separate agent
available under this session's standing instruction. Say so again if it is true. What has
worked in place of a fresh reader, twice, is **hostile inputs through `tests/screen.py`
rather than re-reading**: seven of the seven findings so far came that way, none from
reading code again.

## Record

Every claim of cycle 5's, with a verdict and what was tried against it. Anything found, by
name, with what it would have cost a user. Whether the read was cold. If nothing is found,
what was attacked and came back clean.

**Write no questions into anything.** Decide, record the decision and the reasoning, carry
on.

# Action

Thirty of thirty-three. The three left - AC 19, AC 20, AC 31 and AC 32 - all need the same
thing, and cycle 6 established that the harness does not currently provide it: **a session
that ends after a scheduled job has run.**

The blocker, precisely: any line the reader returns arrives before the timeout that would fire
the job, so the job never fires; a reader that blocks lets it fire, and then nothing can end
the session. Both halves are the queue working correctly.

1. **Give the harness one seam, not the tests a workaround.** The smallest honest change is a
   reader that can be released from outside - a `threading.Event` the test sets once it has
   seen what it came for. It costs one fixture in `tests/`, changes no production code, and it
   is the thing all four remaining criteria are waiting on. **Do not add a sleep**, and do not
   add a parameter to `main` that exists only for tests.
2. **Then AC 32 first, before AC 31.** A job that produces no reply is *not* a failure, and it
   shares a code path with one that is. Getting it backwards means every quiet scheduled job
   reports itself broken, which is worse than not reporting a real failure.
3. **Then AC 31** - a failing job never ends the session - and the rest of AC 30: the failure
   is said, and the next typed line still gets an answer.
4. **Then AC 19 and AC 20** through that same session: a repeating job runs on every match, a
   one-shot runs once and is gone.
5. **Break each one, and read the wall clock as well as the result.** Twice in this loop a
   timing number found what a green suite did not - a spinning thread in cycle 5, a vacuous
   test in cycle 6. A break that makes the suite *faster* has usually made it do less.
6. `uv run pytest` - 699, green.

If step 1 turns out to need production code changed, **stop and say so** rather than changing
it. Four criteria are not worth a seam that exists only because a test wanted one, and the
honest answer may be that these four are settled by manual testing instead.

First thing to tackle: **the releasable reader.** Everything left is behind it, and it is the
only thing standing between this loop and 33 of 33.

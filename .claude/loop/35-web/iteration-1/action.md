# Action

Make axiom name its own sources. Then one live run for AC 7, and the loop is done.

## The sources line

Cycle 4 proved that asking a 7B model to cite addresses produces omission, invention, or
retreat depending on how hard you push - and that inventing is the harmful one. Axiom knows
which addresses were really involved; that is data, not judgement.

Track, per turn:

- every address a search **returned**
- every address a fetch **actually retrieved**, successfully

Those are different, and the difference is the whole point of AC 12. A returned search result
is something axiom saw; a fetched page is something axiom read. **Only fetched pages are
sources.** If the answer used snippets alone, the honest line says the results came from
those addresses without claiming any page was read.

After a turn that used the web, show them. Formatting is `terminal`'s - it owns every print -
and it should be obviously axiom's own line rather than something the model wrote.

**Do not deduplicate away the distinction.** A page that was fetched and failed - 404, timeout,
unreachable - is not a source, and must not appear as one. That is AC 12 in its sharpest form:
the failure this whole cycle was about is presenting an address as read when it was not.

## What to record about the limit

The model can still write an invented address in its prose, and axiom cannot stop it. Say so
in the log, and decide whether the sources line needs to be visibly axiom's - a `VOICE`
prefix - so a reader can tell the trustworthy list from the model's sentences.

Do not claim AC 12 is met in a way that implies the prose is clean. It is met because axiom
provides something true that does not depend on the model.

## Tests

Stub-driven, no network:

- A turn that fetched two pages lists exactly those two addresses.
- A fetch that failed does **not** appear as a source.
- A search that returned five results and fetched none does not claim any page was read.
- A turn with no web use adds no sources line at all.
- The list is per turn, not cumulative across a session - a later answer must not inherit
  the previous question's sources.

## Then AC 7, live

One question that genuinely needs both: search to find a page, then read it to answer. One
run, recorded verbatim. A handful of searches have already been spent; this is one more.

## Record

Full suite and the hermeticity check. The transcript will change - a sources line is a new
observable path - so copy aside, regenerate, diff, and check the diff by command as cycle 3
did rather than by eye. `wc -l` and test count against 1189 and 172.

If all 30 read `met-with-evidence`, **the goal is met**: follow `loop.md` exit 1, then hand
over to the next loop in `queue.md`. #32 is the last one queued.

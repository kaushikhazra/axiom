# Action

AC 24 first - it is small and it is code. Then the live pass, which is everything else.

## AC 24: Ctrl-C during a search or a fetch

#34 found that `run_command` leaked a process on interrupt, because it held a subprocess and
the turn unwound without killing it. `search_web` and `fetch_page` hold a socket rather than
a child.

**Check rather than assume.** An interrupt during `httpx.get` should leave nothing behind -
but that is a claim. Test the world the way #34's timeout test did: assert on what is left
running or open, not on the message.

If there is nothing to clean up, say so plainly with the evidence, and the criterion is met
by the turn loop already catching `KeyboardInterrupt`.

## The live pass

Seven criteria, one model, real network. `qwen2.5:7b` is enough - AC 3 across families is
#34's concern and was settled there; this is about what a model does with search and fetch.

Drive the real program through a pipe, as before. **A handful of searches, not a loop** -
throttling is routine and burning the IP costs the next cycles.

- **AC 2** - ask something needing current information; it searches and answers from results.
- **AC 5** - give it an address; it reads and answers from the content.
- **AC 7** - one question that needs both, answered without prompting between.
- **AC 8** - give an address and confirm **no search happens**. The transcript shows the query
  before a search, so its absence is observable rather than inferred.
- **AC 9** - ask something the snippets alone answer, and confirm no fetch.

Record each run verbatim, including any that misbehave.

## AC 11 and AC 12, honestly

**AC 11** - an answer drawn from the web names the addresses it came from.

**AC 12** - axiom does not present an address as a source unless it actually read that page.

Both are claims about what the *model* does, not what the code does. A model handed five
snippets can name all five as sources having read none.

Try it. Then say plainly which of these is true:

1. The model already behaves. Record the runs; note the sample is small.
2. It does not, and a system prompt fixes it. Add one, say what it says, and re-run.
3. It does not, and a prompt does not reliably fix it. **Then say the criterion cannot be met
   as written** and what would replace it - for instance, axiom listing the addresses it
   actually fetched rather than relying on the model to be honest about it.

Option 3 is a real outcome, not a failure. A criterion that depends on a 7B model's candour
may simply be the wrong criterion, and the honest move is to say so rather than accept one
lucky run as evidence.

## Safety

Read-only. Stable public pages. No live model chooses an address to fetch except through the
normal flow being tested, and nothing destructive is in reach of these two tools anyway.

## Record

Full suite and the hermeticity check afterwards - a live cycle must not leave the suite red.
Status for all 30. If all 30 read `met-with-evidence`, **the goal is met**: follow `loop.md`
exit 1, then hand over to the next loop in `queue.md`.

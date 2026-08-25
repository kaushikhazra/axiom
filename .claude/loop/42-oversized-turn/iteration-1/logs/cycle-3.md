# Cycle 3 — 2026-08-26, 03:28 IST

The external check. It found **two** defects, and the second means this loop does **not**
merge yet.

## Criteria status

| AC | status | note |
|---|---|---|
| 1 | `met-with-evidence` | also attacked with usage *above* the trigger: 7 compactions, 8 turns, 0 refusals |
| 2 | `met-with-evidence` | |
| 3 | `met-with-evidence` | refused once, then five ordinary messages all went through |
| 4 | **`blocked`** | **violated in the conversation-too-large band — see below** |
| 5 | `met-with-evidence` | boundaries attacked; all three causes now in the transcript |
| 6 | `met-with-evidence` | said once, session ends |
| 7 | `met-with-evidence` | transcript diff is purely additive, read in full |
| 8 | `met-with-evidence` | `the summary is full - forgetting 17:` now visible in the transcript |

**Suite: 268 passed**, hermetic.

## Defect 1: the user's message was being compacted away

Found by attacking AC 3. Cycle 2's AC 3 test reported *zero* refusals where one was expected,
which read as a pass and was the opposite.

`maybe_compact` runs **before** the user's line is appended — that ordering is precisely what
keeps compaction to history. `compact_to_fit` runs **after** it, on a list that includes the
line just typed, and at `kept_pairs=0` it compacts everything. Measured:

```
question length : 3358 chars
what the model actually received:
  system   616 chars  'You are axiom, a terminal assistant...'
  system    65 chars  'Summary of earlier conversation:\n- the user asked a long question'

  marker reached the model      : False
```

**The model was sent a prompt and a summary of the question, and no question.** It answered
something it had never seen, and nothing was said about it. That is worse than the refusal it
replaced, and it is the same shape as #40's AC 7 and #41's AC 9 — a criterion whose test
passed for an implementation that did the wrong thing.

Fixed by holding the pending line out of the compaction and passing its length as overhead
instead: compact the history until history + prompt + this message fit together. Two
regression tests, one for the message surviving and one for the history *behind* it still
being compacted — a fix that simply skipped compaction while a message was pending would
have passed the first and undone the issue.

## Defect 2: AC 4 is violated, and this is why the loop does not merge

Adding the transcript scenarios exposed it. In the band where the context is above the floor
but below roughly twice it, the conversation-too-large case does this:

```
> a reply          (x4, turns that worked)
> axiom: compacting older history (everything)
axiom: the summary is full - forgetting 17: ...
> axiom: compacting older history (everything)
> axiom: compacting older history (everything)
> axiom: compacting older history (everything)

error: the conversation so far is about 51 tokens too large ... start a new session   (x4)
```

**Four consecutive refusals of ~80-character messages**, each preceded by a pointless
re-compaction that achieves nothing. AC 4: *"A session cannot reach a state where every
message, however short, is refused."* It reached exactly that.

The advice given is honest and achievable — the user can start a new session. But the
criterion is not about advice, it is about the state existing at all, and cycle 2's fix for
the sub-floor case (end the session) does not apply here: there **is** a conversation, and
ending would throw it away without asking.

**The fix, decided and not asked:** when nothing on the ladder fits, the summary itself is
what will not fit, and letting it go is the only move left that keeps the session usable.
Drop it, and report the facts through the same `note_facts_forgotten` line #32 built for
exactly this — a fact lost silently is the failure that issue exists to prevent. The session
then continues instead of sitting in a state where nothing works.

**It is not implemented in this cycle, deliberately.** Cycle 2's mistake in #41 came from
making a second significant change at speed immediately after the first. The defect is
precisely described, the fix is decided, and cycle 4 implements it with attention. Merging
now with AC 4 knowingly violated would be worse than one more cycle.

## What was attacked and held

| attack | result |
|---|---|
| AC 1 with usage *above* the trigger, so `maybe_compact` already ran | 7 compactions, 8 turns, 0 refusals |
| AC 3 with five ordinary messages after a refusal | 1 refusal, 5 turns, session usable |
| AC 5 at the boundaries — context exactly the prompt's cost, empty message, exact fit | every case in the right bucket |
| Cycle 2's decision to end the sub-floor session | said once, exit status 0 |

**On cycle 2's decision to end the session:** it holds, and there is a fact that makes it
safe which cycle 2 did not state. `what_will_not_fit` returns `CANNOT_CONTINUE` only when the
prompt's cost alone exceeds the context — and both are **fixed for the whole run**. So the
verdict cannot change mid-session: it is either true from the first message or never. Nothing
is ever lost by ending, because no conversation was ever possible. Verified: an empty string,
`"hi"` and a 500-character message all return the same verdict at the same context.

That also means it is decidable at **startup**, before the user types anything. Saying so at
startup would be a stronger reading of AC 6 than saying it after the first message. Recorded,
not built — the criterion is met as it stands and this would be scope it does not carry.

## The transcript gap is closed

The refusal path had never been scripted, which is why AC 7 passed byte-identical in cycle 2
while three new user-visible messages sat outside the behaviour record. Three scenarios added,
one per cause. The whole diff was read as a diff before accepting: **57 lines, purely
additive, no existing line changed.**

Two of the three scenarios were rewritten before being accepted, because the behaviour they
produced did not match the name they were given — the first sizing hit the *message* case
while claiming to show the *conversation* case. A scenario whose title lies is worse than no
scenario.

## Nothing here needs an answer from Kaushik

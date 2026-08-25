# Action

**One job: make AC 4 true in the conversation-too-large band.** Cycle 3 found it violated,
described it precisely, and decided the fix rather than implementing it at speed. Everything
else in #42 is `met-with-evidence`.

## The defect, from `logs/cycle-3.md`

Context above the floor but below roughly twice it. Four turns work, then:

```
> axiom: compacting older history (everything)   (x4, each achieving nothing)
error: the conversation so far is about 51 tokens too large ... start a new session   (x4)
```

Four consecutive refusals of ~80-character messages. **AC 4: "A session cannot reach a state
where every message, however short, is refused."** It reached exactly that.

## The fix, already decided

When nothing on the ladder fits, the summary itself is what will not fit. Let it go.

- In `compact_to_fit`, after the ladder is exhausted: if the payload would fit **without** the
  summary, return the history with it dropped.
- **Report the facts through `note_facts_forgotten`**, the line #32 built for exactly this. A
  fact lost silently is the failure that issue exists to prevent, and this drops more at once
  than any other path.
- The session then continues instead of sitting where nothing works.

Do not end the session here. Unlike the sub-floor case there **is** a conversation, and
ending would throw it away without asking. Cycle 3 established why ending is safe there and
not here: `CANNOT_CONTINUE` depends only on the prompt and the context, both fixed for the
run, so it is true from the first message or never — no conversation is ever lost.

## Then prove it

- **A test for the band itself:** a session that reaches the wall, drops the summary, and
  **carries on** — the next short message must get a reply, not a refusal.
- **A test that the dropped facts are named**, one by one, not counted.
- **The negative:** a session that has *not* reached the wall must not drop anything. This
  path only fires when the ladder is exhausted.
- The transcript scenario `the conversation outgrows what is left...` will change — it is the
  scenario that demonstrates the defect. Regenerate **deliberately** and expect its refusals
  to be replaced by a forgetting line and a reply. **Read the whole diff as a diff.** Nothing
  outside that scenario should move.
- Full suite and the hermeticity command. **268 is the floor.**
- `.tmp/attack_42.py` and `.tmp/attack_42b.py` unchanged.

## Then the cold check on the fix itself

The fix is new code written by the cycle that will also judge it. Before the exit, attack it:

- Does dropping the summary ever lose facts **without** saying so?
- Can it drop the summary when a shorter message would have fit — throwing away history that
  did not need throwing away?
- What happens when the summary is dropped and the payload *still* does not fit? That should
  be `CANNOT_CONTINUE`'s case, not a silent failure.

## Then take the exit

**All eight met:** `loop.md` exit 1. Commit, push, PR referencing #42, merge, delete the
branch. Then in the same run: delete the cron, mark #42 done in `queue.md` with the PR number
and cycle count, and scaffold row 8 — #43, `43-mcp-servers`.

**#43's scaffold carries the MCP clause in `CLAUDE.md`'s testing section**, which binds that
loop specifically: no test fetches a server, the in-memory transport settles nearly
everything, a real process is a script the repo owns, and no test contacts a hosted server or
needs a real secret. It also carries the no-questions rule, stated as decisions.

**Not all eight:** do not merge. Record what is left and write cycle 5's action.

**Write no questions into anything.** Decide, record the decision and the reasoning, carry on.

# Assumptions

Standing inputs. May change between iterations — when one does, say so in that cycle's Observe.

- Python 3.12+. Code lives in `C:/Projects/axiom/src/`. Dependencies managed with `uv`.
- **KISS, not asceticism.** Reach for a good library rather than writing it.
- This continues `src/axiom/__init__.py` from issues #26, #28, and #29's iteration-1 (all on `feature/29-context-compaction`, not yet merged — PR #31). Read it before writing — do not regenerate it.
- **The root cause, established live before this iteration started:** when compaction fires a second time in the same session, `compacted_history()`'s "older" portion can include an *already-compacted* `system`-role summary message from the previous pass. That gets handed to `compact()` again, mixed in with newer raw turns, and re-summarized as one blob — the model produced a fresh summary that dropped a fact ("teal") the first summary had correctly preserved. Confirmed live, not theoretical: a real transcript showed the second compaction firing, followed by an incorrect answer to a question the first compaction had answered correctly moments before.
- **The fix approach is not locked — Kaushik explicitly deferred it to the loop rather than deciding it upfront.** One candidate, offered but not confirmed: never re-summarize an existing summary — if the block being compacted already starts with a prior `system`-role summary, carry it forward verbatim and only summarize the genuinely new turns since then, appending rather than re-compressing. Try this first as the most root-cause-oriented option (structural, not a soft prompt instruction), but the loop should judge by live evidence, not commit to it just because it was proposed first.
- `AXIOM_DEBUG_MAX_CONTEXT` (env var, added this session) overrides the computed effective context — this is what makes triggering repeated compaction practical to test without needing tens of thousands of tokens of real conversation. Use natural, varied sentences as filler, never repeated/near-identical text — a repeated 3-word phrase sent the model into a degenerate repetition loop earlier this session, unrelated to axiom's own logic.
- `pytest`, tests in `C:/Projects/axiom/tests/`.
- Loop engineering, not spec-driven. Do not write `requirement.md`, `design.md`, or `task.md`, and do not run the `/e-spec:*` or `/dryrun-*` skills.
- Read `C:/Projects/axiom/CLAUDE.md` before the first write.
- **Work happens on `feature/29-context-compaction`, already checked out.** Never `master`.
- Commit each cycle's work. Plain pushes are allowed; force-pushes and tag pushes are blocked by a hook and must be left to Kaushik.

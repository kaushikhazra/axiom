# Goal

Let a user keep chatting after axiom refuses a turn for being too large - meeting every one
of the 8 acceptance criteria on GitHub issue #42.

#29 gave axiom automatic compaction, #32 bounded the summary so it could not itself overflow,
and both left one hole: the size check that decides whether to send at all runs **after**
compaction has had its chance, and when it refuses there is nothing left to try. The turn is
dropped, and the next one meets the same wall.

The failure is not one refused message. It is a session that cannot be continued and does not
say so - every later message refused, however short, with no way back and nothing telling the
user that retrying is pointless.

**#41 made this reachable rather than theoretical.** It added a system prompt to every
request, ~163 tokens under the conservative divisor, and that is a fixed cost the user cannot
shorten by typing less. There is a one-line reproduction: `AXIOM_DEBUG_MAX_CONTEXT=200`, then
type anything at all.

Done when: all 8 criteria of #42 are met, each with evidence recorded in a cycle log; the
recovery criteria are evidenced by a real session driven into the refusal and back out of it,
not by a unit test asserting our idea of it; and a turn that fits is provably unchanged.

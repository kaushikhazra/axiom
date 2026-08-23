# Action

Cycle 4 produced the evidence for what comes next: a 400,000-character message ran for over five minutes with no output whatsoever. A slow generation is currently indistinguishable from a hang. That is AC 5, and it is now demonstrated rather than assumed.

Stream the reply instead of waiting for it whole. Tokens appearing as they arrive is what makes generation visibly in progress, and it is the same change that creates the partial-output state AC 15 is about — a stream that dies mid-reply must not leave the user thinking they read a finished answer.

Target AC 5, and settle the two criteria that have been untested since cycle 1: AC 4 and AC 15.

Evidence to produce: a transcript of a deliberately long generation showing output arriving progressively, not in one block at the end · that same long reply shown complete and untruncated, with the tail of it visible · a stream interrupted part-way — reuse `scratchpad/flaky_proxy.py`, adapted to cut the connection mid-response — showing the user is told the reply was cut off rather than being handed the fragment as if it were the whole answer.

History must store what was actually received, and a cut-off reply must not enter history as though it were complete.

Leave Ctrl-C alone this cycle. It is the last one, and it is easier to reason about once generation is a stream.

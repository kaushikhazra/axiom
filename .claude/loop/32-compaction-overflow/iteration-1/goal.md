# Goal

Let a user keep chatting indefinitely without the compacted history itself eventually
overflowing the context - meeting every one of the 6 acceptance criteria on GitHub issue #32.

#29 stopped history growing without bound by summarizing it. #32 is the failure that leaves
behind: the summary itself only ever grows, and a long enough session ends with a summary
that cannot fit. Nothing today notices, and Ollama truncates silently.

Done when: all 6 criteria of #32 are met, each with evidence recorded in a cycle log, and the
ones about overflow are evidenced by a real session driven far enough to reach the boundary -
not by a unit test asserting our idea of it.

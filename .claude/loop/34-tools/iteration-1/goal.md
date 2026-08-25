# Goal

Give axiom tools, so that a user can ask it in chat to read and change files and to run
commands on their machine, and it does the work rather than describing it - meeting every
one of the 35 acceptance criteria on GitHub issue #34.

The hard part is not any single tool. It is that tool calling must work the same way across
models that announce their calls differently, with no per-model branch anywhere in the code.

Done when: all 35 criteria of #34 are met, each with evidence recorded in a cycle log, and
the multi-model criteria are evidenced by real runs against real models rather than stubs.

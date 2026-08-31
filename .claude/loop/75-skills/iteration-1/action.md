# Action

**Build `/skill` and `/skills`.** Six criteria, AC 5 to AC 11, and they are the last part of
the feature a user touches directly.

They sit beside `MODEL_COMMAND` in `src/axiom/__init__.py` and are handled in the same place
`/model` is - before `terminal.start_turn()`, so a command that never becomes a turn leaves
no stray gap on screen. That placement is already load-bearing for #60's AC 7 and AC 8; put
these inside it rather than beside it.

- **AC 5** - `/skills` lists every loaded skill, name and description, one to a line.
- **AC 6** - with none loaded, say so *and* say where a skill would go. Both halves.
- **AC 7** - `/skill <name>` puts the instructions into the conversation and **starts a
  turn**.
- **AC 8** - `/skill <name> <text>` takes the trailing text as the request.
- **AC 9, AC 10** - no name, or an unknown name: list what is available and **send nothing
  to the model.**
- **AC 11** - the user sees which skill is in use *before* the reply begins.

**AC 9 and AC 10 are the ones a test will half-do.** A command that prints the right thing
and *also* starts a turn looks correct on screen and fails both criteria. Assert on
`StubBackend.streamed` being untouched, not on what was printed. That is the same seam the
AC 13 test already uses and it is the only one that can tell the difference.

**AC 11 needs `terminal.py`, and axiom's voice rules bind.** #60 AC 17 and AC 29 govern how
axiom's own lines stay distinguishable from the model's; a skill announcement is axiom
speaking, so it uses `VOICE` and does not invent a fourth voice. Look at how
`note_tool` announces a tool call and follow it - AC 14 says the model invoking a skill is
shown "the way a tool call is shown", so the two should not end up looking different.

Run the break on each before counting it. For AC 7, the break that matters is a command
that loads the instructions but does not start a turn - it will look like it works.

Do not start on configuration (AC 36 to AC 39) or compaction (AC 34, AC 35) yet. The off
switch has to know what it is switching off, and two of the three things it disables are
these commands.

First thing to tackle: **`/skills`**, because listing is what makes every other command
testable by hand, and AC 6's "say where a skill would go" is the only line in the feature
that tells a new user how to start.

# Action

**Build the off switch and the startup lines.** Seven criteria that go together, because
each one is about what the user is told and what they are charged.

- **AC 36, AC 37** - skills on by default; a flag and an environment variable turn them off,
  and the flag wins. `--no-web` and `--no-mcp` in `src/axiom/config.py` are the pattern,
  down to the `OFF_VALUES` handling. Follow it exactly.
- **AC 38** - with skills off: **nothing about any skill reaches the model**, `/skill` and
  `/skills` say so, and the per-request cost is not paid. Three separate things. The third
  is the one that gets faked - assert the declared tool count, not the message.
- **AC 2, AC 39** - the startup line says how many skills loaded, beside the tool count, and
  whether skills are on at all.
- **AC 3** - what the skills add, in tokens. `note_tool_cost` already reports the total and
  `_tool_cost` already includes the catalogue; what is missing is naming the skills' share
  separately, so a user can weigh keeping one.
- **AC 4** is proven at the loader but its startup half is not: a skill that could not load
  is **named on the startup line with its reason**. `note_servers` already does exactly this
  for MCP problems - use the same shape, not a new one.

**Run narrow breaks.** Three cycles running, a break big enough to be easy to write has
taken several tests with it and proved nothing about the criterion it was aimed at. For each
of these, break the one thing: drop the count from the line, drop the token figure, leave the
problems out, make the flag lose to the variable.

**AC 38's first clause deserves its own test at the `streamed` seam.** "Nothing about any
skill reaches the model" with skills off is the same assertion as AC 13's and should reuse
`everything_sent` - a catalogue that is empty because the feature is off must be
indistinguishable, in the payload, from one that is empty because there are no skills.

After this, what remains is AC 14, 15, 16 (the live-model measurement), AC 25, 29, 31, 32,
34, 35, 43, 44. **AC 15 and AC 16 need real models and have not been started** - they are the
long pole, and the cycle after this one should begin them rather than leaving them to the
fail-safe.

First thing to tackle: **`--no-skills` and `$AXIOM_SKILLS`**, because AC 38's three clauses
and AC 39's line all describe what happens once it exists.

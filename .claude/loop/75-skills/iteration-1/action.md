# Action

The catalogue is settled and break-proven. Build the four tools on top of it.

`read_skill`, `write_skill`, `delete_skill`, `invoke_skill`, declared in `REGISTRY` in
`src/axiom/tools.py` exactly the way the existing seven are. They need the catalogue, which
`Limits` cannot carry - it is frozen and holds settings that belong to the user, while the
catalogue is mutable session state that a write has to refresh. `#74` hit this exact
problem and solved it with a `needs_schedule` flag beside `needs_limits`. **Follow that,
do not invent a second mechanism.**

What each has to do, in the criteria's terms rather than in code:

- **read** returns the file as written, frontmatter included (AC 17). Not the body -
  `instructions()` already returns the body, and read is the one that has to show the
  frontmatter so a model can edit it.
- **write** creates or replaces, validates before it writes, and **refreshes the
  catalogue** so the skill is listed and invocable in the same session (AC 18, AC 19).
- **delete** removes and refreshes, so the skill leaves the list at once (AC 20).
- **invoke** returns `instructions()` and nothing else (AC 13).

**Validation is the whole reason these are tools rather than `write_file`.** A write with
missing or malformed frontmatter is refused, the refusal names the field, and nothing
reaches disk (AC 21). `_one` already produces exactly those messages - reuse it rather than
writing a second set of rules that will drift from the loader's.

**AC 42 - a refused write leaves the previous version untouched - is the one to get right
by construction**, not by remembering: validate the new text before opening the file for
writing, so there is no path where a bad write has already truncated a good skill. Settle
it with a stub client inside `tmp_path`, as CLAUDE.md requires. Never ask a live model to
improvise a malformed file.

Run the break on each tool before counting it. The one most likely to be vacuous is AC 19 -
a test that writes twice and reads back will pass whether or not the catalogue refreshed,
because reading goes to disk either way. **Assert on what the model is told next**, not on
the file.

Leave `/skill` and `/skills` for the cycle after. They are a different seam - the REPL, not
the registry - and mixing them in makes both harder to break-test.

First thing to tackle: **`needs_schedule`'s twin for the catalogue**, because all four
tools need the session's catalogue and none of them can be written until there is a way to
hand it to them.

# Assumptions

Standing inputs. May change between iterations — when one does, say so in that cycle's Observe.

- **Four tools, and a slash command as well.** Kaushik's call, and the reason is the format:
  a skill is not a file, it is a folder with frontmatter that has to parse, so the generic
  file tools cannot validate one or refresh the catalogue after a write. The model gets
  read, write, delete and invoke. The user gets `/skill` and `/skills`. `REGISTRY` in
  `src/axiom/tools.py` is the pattern for the four; follow it exactly.
- **Invoke means the instructions enter the conversation.** Not a sub-agent, not a second
  loop, not its own context. The body arrives the way a tool result arrives and the model
  carries on in the same turn. This was chosen against the sub-agent reading deliberately.
- **`/skill <name> [text]`, not `/<name>`.** Namespaced so a skill called `model` or `exit`
  can never shadow a built-in. `/skills` lists. Both sit beside `MODEL_COMMAND` and
  `EXIT_COMMANDS` in `src/axiom/__init__.py` and are handled before the turn starts, the way
  `/model` already is.
- **Project scope only: `.axiom/skills/{name}/SKILL.md`.** Beside `mcp.json` and
  `model.json`, resolved at runtime relative to the working directory. No personal
  directory and no configurable path — both were considered and dropped for now.
- **Frontmatter carries `name` and `description`; anything else is ignored, not refused.**
  That is what makes AC 24 true: a `SKILL.md` written for another agent loads unchanged.
  Ignoring is a decision, not laziness — refusing unknown fields would break interop for
  nothing.
- **Use a library for the frontmatter.** CLAUDE.md is explicit that minimal does not mean
  rewriting what a good library already does, and hand-rolled YAML is exactly the trap that
  rule names. Adding one to `pyproject.toml` is expected, not a deviation. `croniter` went
  in for #74 on the same reasoning.
- **The catalogue is name and description only, and it is built once at startup.** The body
  is read from disk at the moment of invocation (AC 33) — which is also what makes an edit
  mid-run take effect, and what makes AC 41 a real failure with something to say.
- **Live-model tests do not run in the hermetic suite.** AC 15 and AC 16 need real models
  and real latency; the other 42 criteria must stay fast and offline. Separate them from
  the first cycle — a marker, a directory, or a flag — not at the end when the suite has
  already slowed down.
- **AC 15 and AC 16 are measured against every model `ollama list` reports**, not against a
  favourite. A model that cannot reach for a skill reliably is a number in the log, and the
  goal still converges. This mirrors #68's shape deliberately.
- **CLAUDE.md's "Testing tools before security exists" has a #75 paragraph. Read it.** A
  skill is the first thing axiom writes that outlives the run that wrote it. Test-created
  skills go under `C:/Projects/.tmp/axiom-tool-sandbox`, never `.axiom/skills/` in this
  repo. A refused write and a delete are settled with a stub client, not by asking a live
  model to improvise a bad file.
- **The source is `src/axiom/` and the tests are `tests/`.** This iteration folder holds the
  loop's own files and logs, nothing else. Never copy source into it.
- **Nothing here touches `schedule.py` or `_as_markdown`.** #74's scheduler and #72/#73's
  renderer are merged and settled; this story has no business in either.
- **`master` now carries #72, #73 and #74 — 775 tests.** That is the baseline this branch
  starts from, and the count arithmetic in `observe.md` starts there.

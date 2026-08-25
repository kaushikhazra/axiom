# Assumption

Standing inputs. These are given - do not re-derive them, and do not spend a cycle deciding
them.

## The codebase this lands in

#33, #34, #35, #32 and #40 all merged. `src/axiom/` is seven modules; **229 tests, green and
hermetic** at scaffold time.

- **There is no system prompt today.** `main()` starts with `messages: list[dict[str, str]]
  = []` and the first thing appended is the user's line. The only system message that ever
  appears is the one `compaction.compacted_history` inserts to carry a summary. **AC 1
  introduces axiom's first system prompt**, which is the largest structural change in this
  issue and the one most likely to have side effects.
- **`compaction.py` treats a leading system message as a carried-forward summary.**
  `compacted_history` checks whether `older` begins with a system message and appends newly
  summarized facts to it. Measured in cycle 1, with a permanent prompt at index 0: it
  survives one compaction, five compactions, and #32's `bounded()`. Two things spoil it:
  - **A leading system message suppresses the summary header.** The `"Summary of earlier
    conversation:"` line is only added in the `else` branch, so the conversation's facts get
    appended straight onto the prompt with nothing labelling them. That header is
    deliberate - its own comment explains it sits on its own line so dropping the oldest
    fact cannot take it away.
  - **`bounded()` keeps the front of the string**, so a prompt at index 0 survives by
    accident of #32's choice to forget the middle. Nothing records the dependency, and a
    future change to the bounding strategy would start eating the model's limits silently.
- **Decided in cycle 1: the system prompt lives outside `messages`** and is prepended at
  send time. Compaction never sees it, the header logic is untouched, and `bounded()` gains
  no hidden dependant. **`estimated_tokens` and `too_large` must count it**, or the size
  check under-counts by exactly the prompt on every turn - flag this to #42, which owns that
  check.
- **`MAX_TOOL_ROUNDS = 8` in `__init__.py`**, with a comment explaining why it is eight and
  not five. AC 10 is about what the user is told when the loop exhausts it: today the `for
  _round in range(...)` simply ends and whatever `reply` holds is shown, which may be
  nothing at all.
- **`Limits` is never model-visible**, deliberately, and `tools.run()` refuses any argument a
  tool did not declare in its schema. **AC 3 is therefore already true structurally** - the
  work is evidencing it, not building it.
- **`terminal.note_tool(call.name, call.arguments)` already prints every call and its
  arguments before `tools.run` is called.** AC 6 asks for a path outside the working
  directory to be visible before the tool runs; a path is already visible. The question is
  whether *outside* is distinguishable, not whether anything is shown.
- **`limits.working_directory` reaches `run_command` as `cwd`, and nothing else.** File
  tools use `Path(path)` directly, so they resolve against the process's own directory, not
  against `Limits.working_directory`. That difference is real and predates this issue.
- **The two messages AC 7 and AC 8 are about, exactly as they read today:**
  - `error: still running after {N:g} seconds - stopped it`
  - `[cut here - {N} more characters not included]`
- **`terminal.py` owns every print.** Nothing else writes to stdout.
- **`tests/conftest.py`** holds `StubBackend`, `feed()`, `chunk()`, `vendor_call()` and the
  autouse fixture clearing `AXIOM_HOST`, `AXIOM_MODEL` and `AXIOM_DEBUG_MAX_CONTEXT`.
- **`httpx.Response(status, text=...)` stamps `content-type: text/plain; charset=utf-8`**
  (#40 cycle 2). Any stubbed response must set its type explicitly or it is testing a
  contradiction. `given_page` and `stub_fetch` already do.

## Given

- **`requires-python = ">=3.12"`; the venv is 3.14.3.** `uv` and pytest.
- **Dependencies are `ollama`, `httpx`, `psutil`, `ddgs`, `trafilatura`.** A new one needs a
  stated reason. This issue almost certainly needs none.
- **`axiom:main` stays the packaging entry point.**
- **The repo's own rules apply**: KISS over structure, one command per shell invocation,
  nothing committed under a `temp` name, project-local `.tmp/`, loop files stay in this
  folder while code stays in `src/` and `tests/`.
- **The branch is `feature/41-limits-and-place`.** Commits reference #41.
- **#42 and #43 follow.** #42 reaches into compaction and the size check; #43 adds MCP tools
  and a config file. A system prompt that hard-codes "seven tools" or assumes a fixed tool
  list will be wrong in two loops - **describe the limits, not the inventory.**

## Decided - do not reopen

Settled here so no cycle spends itself on them. Both follow the criteria as written.

- **AC 4 and AC 5 are one instruction, not two mechanisms.** The model is *told* to keep work
  inside the working directory and to go outside only when the user names a path outside.
  There is no enforcement layer in this issue - no path guard, no refusal. AC 5 exists
  precisely to stop one being built: a path the user named must still be honoured wherever
  it points. Enforcement belongs to the unlanded security stories, not here.
- **AC 6 is visibility, not permission.** The path is shown before the tool runs. Nothing is
  blocked, nothing is asked. If showing it requires knowing what "outside" means, resolve
  both sides and compare - do not invent an approval step.

## Carried forward, worth not relearning

- **Probe before designing.** Every significant decision in #34, #35 and #40 that was probed
  first held; the ones reasoned from the code alone were wrong. #40's whole existence was a
  library assumed to be more general than it is.
- **A test can prove the happy path of a criterion and miss the criterion.** #40's AC 7 was
  marked met by a test that served a text body to a code path that was supposed to *judge*
  bodies. It passed for an implementation doing no judging at all.
- **A scripted `.replace()` that does not match reports success.** It has happened four
  times across this queue. Verify scripted edits landed.
- **Test the world, not the message.** #34's timeout reported "stopped it" while the command
  kept running. This issue is *entirely* about messages, which makes the rule harder and
  more important: assert on what changed, not on what was said about it.
- **A criterion can turn out to be wrong.** #35 replaced one on evidence and #32 amended
  three. Saying so with measurement is a result, not a failure.

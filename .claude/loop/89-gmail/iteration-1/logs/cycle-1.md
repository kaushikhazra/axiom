# Cycle 1 — the read pass

2026-09-10, 21:52 IST. The artifact existed before the loop did, so this cycle reads and
records. Nothing in `src/axiom/` or `tests/` was touched.

## The count

**0 of 40 criteria met.** Nothing is built. That is the expected reading and it is the
number the next cycles have to move.

The useful split is not met-versus-unmet but **what existing machinery already answers**
against **what has to be written**:

| | criteria | |
|---|---|---|
| Downstream of machinery that already exists | 1, 2, 21, 23, 24, 25, 36, 38 | a filter, a notice, a precedent — wiring, not invention |
| Genuinely new code | 4–14, 17–20, 26, 32–34 | the flow, the client, the four tools, the shapes |
| **New surface with no precedent at all** | **15, 16, 22** | there is no `/mail` command and nothing like one |
| Negatives, provable only by a sweep | 27–31, 35, 37, 39, 40 | see `observe.md` |
| Owed to a live account | 12 | and 3, 11 partially |

## What a new tool has to look like

`Tool` is a frozen dataclass — `name`, `description`, `parameters` (JSON Schema), `run`,
and three injection flags. `REGISTRY` is a module-level dict comprehension over a literal
tuple at `tools.py:600`, built at import time. `declarations()` emits every entry
unfiltered; `run()` looks the name up, **refuses any argument the schema did not declare**,
and turns every exception into `error: ...` rather than raising.

So a Gmail tool is one more `Tool(...)` in that tuple. There is no registration step, no
plugin point, and nothing to invent. **That is the whole shape**, and it is what
`action.md` asked for.

## The one structural obstacle

`run()`'s dispatch is an **exclusive chain**:

```python
if tool.needs_limits:   return tool.run(**arguments, limits=limits)
if tool.needs_schedule: return tool.run(**arguments, jobs=jobs)
if tool.needs_library:  return tool.run(**arguments, library=library)
return tool.run(**arguments)
```

A tool gets **at most one** injected dependency. A Gmail tool needs a session-scoped
authenticated client, which is a fourth. `needs_schedule` and `needs_library` were both
added for exactly this reason and their docstrings give the same argument — session state,
not user settings, and not something a model can reach by naming it. A fourth flag follows
the precedent rather than bending it.

**The exclusivity holds**, and that is worth checking rather than assuming: no Gmail tool
needs `limits`, because AC 31 says a message body is never written to disk, so nothing
resolves a path. If a later criterion forces a tool to need both, the chain becomes the
problem and not the flag.

## AC 29 and AC 30 have a structural answer, not a vigilance one

The only path from a tool call to the screen is `_called(name, arguments)` in
`note_tool` (`terminal.py:1823`), which prints the arguments verbatim.

A credential cannot travel that path — not because anyone remembers to redact it, but
because it arrives by injection and is never a declared parameter, and `run()` refuses any
argument a tool did not declare. **A token cannot be an argument, so it cannot be
printed.**

That narrows the sweep considerably. AC 29 and AC 30 are about the **error paths**: what a
`google.auth` exception carries when `run()` catches it and returns `error: {failed}`, and
what an `HttpError` puts in its string. Those are the places to read, not the call line.

## AC 21 is already built

`note_tool` draws the call before the tool runs and `_start_working` puts a transient
`· gmail_search ...` line under it, taken back when the result lands. #85 built this. The
Gmail tools inherit it by being tools. Nothing to write.

## AC 37 is *not* covered by the existing discipline

`terminal.py` guards ten sites on `_rendering and sys.stdout.isatty()`, and #74's pass
found the one function that had missed it. **None of that reaches
`InstalledAppFlow.run_local_server()`**, which opens a browser from inside a library, in a
module that does not exist yet.

So AC 37 is a guard at a new call site, not a sweep of an old one. Naming it now because
"the codebase already has the isatty discipline" is exactly the sentence that would let it
be skipped.

## Precedents worth copying rather than re-deriving

- **AC 1, AC 2, AC 36** — `_prepare()` (`__init__.py:295`) is already a filter chain:
  `--no-tools` drops everything, `--no-web` drops `WEB_TOOLS`, and
  `_without_unusable_skill_tools` drops what a run cannot use. #75 measured why — four
  unusable skill tools cost **396 tokens on every request**, taking the total from 1111 to
  1507. A `MAIL_TOOLS` frozenset and one more filter step is the same move.
- **AC 23, AC 24, AC 25** — `Settings.mcp_problems` is the precedent, and its comment is
  the reasoning: *"Named one by one rather than counted: a variable the user has not set is
  fixed by setting that variable, and a count does not say which."* A missing, malformed,
  and rejected credential are three different sentences, not one count.
- **AC 15, AC 16, AC 22** — the command dispatch (`__init__.py:748`) is a flat if-chain on
  a single-line `command`, one branch each, with `/skills` matched by **equality before**
  `/skill` is matched by prefix. `/mail` follows it. This is the only genuinely new surface
  in the issue.

## Assumptions

None changed.

## Suite

Baseline run started this cycle; the number lands in cycle 2 rather than being guessed
here. The standing figure from the last handoff is **964 passed, 1 deselected, ~140s**.

## Where this leaves the next cycle

Everything above is downstream of one decision: **where the authenticated Gmail client
lives and how it reaches a tool.** The tool signatures follow from it, and the tool
signatures determine the schema, the filter, the error strings and the sweep. That is the
next action.

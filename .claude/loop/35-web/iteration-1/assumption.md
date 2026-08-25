# Assumption

Standing inputs. These are given - do not re-derive them, and do not spend a cycle deciding
them.

## The codebase this lands in

#33 merged (PR #36), #34 merged (PR #37). `src/axiom/` is seven modules and 1021 lines:
`config`, `context`, `compaction`, `backend`, `terminal`, `tools`, and `__init__` holding the
chat loop and `main()`. 131 tests.

- **Tools already work.** `tools.REGISTRY` holds five, declared once via `declarations()`,
  executed by `run(name, arguments, limits)`. **Search and fetch are two more entries in that
  registry** - the machinery, the visibility lines, the truncation, the failure reporting and
  the multi-round loop already exist and are tested. This loop should be adding tools, not
  building a second mechanism.
- **`Limits` carries operational settings** a tool may need and is never model-visible;
  `run()` refuses any argument a tool did not declare. Fetch timeouts and result counts
  belong there, not in a tool's schema.
- **`backend.call_from_text()`** handles models that announce calls as text. Nothing about
  web tools changes that.
- **`terminal.py` owns every print.** `note_tool` already shows what is about to run, and
  `show_tool_result` marks and truncates output. AC 13, 14 and 15 may already be satisfied by
  what exists - check before building.
- **`tests/conftest.py`** holds `StubBackend`, `feed()`, `chunk()`, `vendor_call()` and the
  autouse fixture clearing the three `AXIOM_*` variables.

## Given

- **DuckDuckGo, with no API key and no account** - that is what AC 24 encodes, and it is the
  reason the provider was chosen. The practical library is **`ddgs`** (renamed from
  `duckduckgo-search`); it needs no key. **Confirm the current package name and API before
  depending on it** rather than trusting this note.
- **Throttling is routine, not exceptional.** DDG returns 202 and 403 after rapid requests
  and holds the IP for a while. AC 16 exists for that, AC 10 exists because of it, and a
  cycle that hammers it will lose the ability to test at all for a period. **Budget live
  searches carefully - a handful per cycle, not a loop of them.**
- **Fetching needs an HTML-to-text step.** `httpx` is already a dependency for the transport.
  Something is needed to turn a page into readable text (AC 6) - reuse before build, and say
  in the log what was considered.
- **Python 3.12, pytest, `uv`.** New dependencies allowed with a stated reason.
- **`axiom:main` stays the packaging entry point.**
- **The safety rules in `CLAUDE.md` bind every cycle**, restated in `observe.md`, plus the
  SSRF note there: an arbitrary-URL fetcher can reach the local network, this loop does not
  fix that, and it must be recorded rather than quietly patched.
- **The repo's own rules apply**: KISS over structure, one command per shell invocation,
  nothing committed under a `temp` name, loop files stay in this folder while code stays in
  `src/` and `tests/`.
- **The branch is `feature/35-web`.** Commits reference #35.

## Carried from #34, worth not relearning

- **A scripted `.replace()` that does not match reports success.** It happened twice in #34.
  If an edit is scripted, verify it landed.
- **Probe before designing.** Every significant #34 decision that was probed first held; the
  one hypothesis reasoned from the code was wrong.
- **A test that asserts on a message can pass against a program that lies.** #34's timeout
  reported "stopped it" while the command kept running. Where a criterion is about the world
  rather than the wording, test the world.

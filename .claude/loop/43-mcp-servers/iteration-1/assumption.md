# Assumption

Standing inputs. These are given - do not re-derive them, and do not spend a cycle deciding
them.

## The codebase this lands in

Every earlier row merged. **272 tests, green and hermetic** at scaffold time.

- **`tools.REGISTRY` is a module-level dict built at import**, and `declarations()` flattens
  it into Ollama function declarations. Both are static today. **#43 is the first thing that
  makes the tool set vary per run**, and `REGISTRY` being import-time is the main structural
  obstacle.
- **`tools.run(name, arguments, limits)` is synchronous and returns a string.** It never
  raises: a failure comes back as `error: ...` text for the model to act on. `Tool.run` is
  declared `Callable[..., str]`.
- **`tools.Limits` is never model-visible**, and `run()` rejects any argument a tool did not
  declare. #41's system prompt is built from the same `Limits`, so anything MCP adds to what
  the model is told has to come from one place, not two.
- **`tools.system_prompt(limits)` deliberately names no tools and no count** - written that
  way for this issue. It must stay that way.
- **`terminal.py` owns every print**, including `announce()`'s startup line, which already
  reports the tool count and whether the web is on.
- **`config.resolve(argv)` is command line, else environment, else default.** There is **no
  config file anywhere in axiom today**. #43 introduces the first one.
- **`tools._kill_tree(pid)` already exists**, using `psutil`, written for #34's command
  timeout because killing a shell leaves its grandchildren running. AC 26 and AC 27 are the
  same problem and this is the tool for it.
- **`tests/conftest.py`** holds `StubBackend`, `feed()`, `chunk()`, `vendor_call()`,
  `history()` and the autouse fixture clearing the three `AXIOM_*` variables.

## The library

Researched before the issue was written; do not re-research.

- **The official `mcp` Python SDK, v2**, tracking the 2026-07-28 spec. One `Client(target)`
  object, an async context manager.
- **Targets:** a URL string (Streamable HTTP), `StdioServerParameters(command, args, env)`
  for a subprocess, **an in-memory server object**, or a custom transport.
- `await client.list_tools()` gives each tool's `name`, `title`, `description`,
  `input_schema`. `input_schema` is JSON Schema, which is what Ollama declarations already
  carry - a direct map.
- `await client.call_tool(name, arguments)` returns `CallToolResult` with `.content` (a list
  of `TextContent` / `ImageContent` / `AudioContent` / `ResourceLink` / `EmbeddedResource`),
  `.structured_content`, and `.is_error`.
- **Tool errors do not raise.** They come back with `is_error=True` and the message in
  `content`. That matches `tools.run()`'s existing contract exactly.
- **The SDK is async-only, and axiom is entirely synchronous.** This cannot be papered over
  with `asyncio.run()` per call, because a stdio server is a subprocess that must stay alive
  between calls and a persistent session needs a live event loop. The known answer is a
  background event-loop thread. **It is invisible to the user and is most of the work.**
- **stdio `env` is an allow-list** plus what is passed: `HOME`, `LOGNAME`, `PATH`, `SHELL`,
  `TERM`, `USER`.

## Given

- **`requires-python = ">=3.12"`; the venv is 3.14.3.** `uv` and pytest.
- **Adding `mcp` is the one new dependency this issue is allowed**, and it is the reuse the
  repo rules ask for - do not hand-roll a JSON-RPC client.
- **`axiom:main` stays the packaging entry point.**
- **The repo's own rules apply**: KISS over structure, one command per shell invocation,
  nothing committed under a `temp` name, project-local `.tmp/`, loop files stay in this
  folder while code stays in `src/` and `tests/`.
- **The branch is `feature/43-mcp-servers`.** Commits reference #43.
- **This is the last row in the queue.** A converged run says so rather than scaffolding
  nothing silently.

## Decided - do not reopen

Settled when the issue was written, from research. Implement them; do not re-decide them.

- **Tools only.** Not resources, not prompts. Those are separate stories.
- **stdio only.** No Streamable HTTP, no OAuth. Local subprocess servers.
- **Every tool is prefixed with its server's name**, always - not only on collision, so a
  server's tool has the same name whatever else is configured.
- **`.axiom/mcp.json` in the project, and `--no-mcp` to switch it off**, mirroring
  `--no-tools` and `--no-web`.
- **Connect at launch, before the first prompt**, so the startup line can report truthfully.
- **`${NAME}` in config is replaced from the environment**, so the file holds no secret.
- **A server that fails to start does not stop axiom.** It starts without it and says which
  failed - consistent with `tools.run()` returning failures rather than raising.
- **A server that dies mid-session fails its own tools and nothing else.**

## Carried forward, worth not relearning

- **Probe before designing.** Every significant decision in #34, #35, #40, #41 and #42 that
  was probed first held; the ones reasoned from the code alone were wrong.
- **A test can prove the happy path of a criterion and miss the criterion.** #40's AC 7,
  #41's AC 9 and #42's AC 3 were all marked met by tests that could not have failed.
- **A stub that contradicts the thing under test proves nothing.**
- **Read a diff as a diff**, and check for removed lines explicitly.
- **A scenario name that does not match its behaviour is read as evidence of something that
  is not happening.**
- **Check which function a number came from.** `estimated_tokens` divides by four and
  `too_large` by three; the system prompt was quoted at 56, then 163, before being measured
  at 205.
- **A scripted `.replace()` that does not match reports success.** Verify scripted edits.

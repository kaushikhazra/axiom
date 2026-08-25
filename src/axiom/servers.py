"""Tools that come from someone else's process.

`tools.py` is what axiom can do. This is about talking to a server axiom did
not write, over stdio, and presenting what it offers as though it were one more
tool - so the chat loop does not have to know the difference.

The SDK is async and axiom is not. A stdio server is a subprocess that has to
stay alive between calls, so a persistent session needs a live event loop -
which means one loop, on its own thread, for the whole run. Measured at 1.21 ms
per call, which is why this is not worth avoiding.
"""

import asyncio
import os
import threading
from contextlib import AsyncExitStack

from mcp import Client, StdioServerParameters
from mcp.client.stdio import stdio_client

from .config import ServerSpec

# `server__tool`. Two underscores because a single one is ordinary inside a
# tool name and would make the split ambiguous. The prefix is both the
# collision guarantee and the routing key - one mechanism, not two.
SEPARATOR = "__"

# How long a server may take to start, and how long one call may take. Bounded
# because a server that never answers would otherwise hang the turn with no way
# back, and axiom's other waits are all bounded already.
START_TIMEOUT = 30.0
CALL_TIMEOUT = 60.0


def qualified(server: str, tool: str) -> str:
    return f"{server}{SEPARATOR}{tool}"


def split(name: str) -> tuple[str, str] | None:
    """A qualified name back into its server and its tool, or None.

    **Not used for routing.** Splitting a qualified name is ambiguous and
    cannot be made otherwise: `a__b__ping` is server `a` with tool `b__ping`
    just as readily as server `a__b` with tool `ping`, and both are legal.
    Cycle 4 found a server whose name contained the separator declaring three
    tools that were then permanently uncallable, because routing partitioned
    at the first one and looked for a server that did not exist.

    Routing uses `_owner`, a map built when the tools are declared, so no
    parsing happens and no name can be misrouted. This is kept because reading
    a name apart is still useful, and it is honest about being a guess.
    """
    server, found, tool = name.partition(SEPARATOR)
    return (server, tool) if found and tool else None


def as_text(result) -> str:
    """A CallToolResult as the one string the chat loop passes around.

    Text blocks joined. **A block that is not text is named rather than
    dropped**: a model told nothing came back answers from memory instead of
    saying it could not read the thing, which is the failure #40 exists to
    prevent.

    `is_error` becomes the same `error:` prefix every other failure uses, so
    the chat loop and the model treat it like any other tool that could not do
    its job.
    """
    pieces = []
    for block in result.content or []:
        text = getattr(block, "text", None)
        if text is not None:
            pieces.append(text)
        else:
            kind = getattr(block, "type", type(block).__name__)
            pieces.append(f"[{kind} content, which cannot be shown as text]")
    joined = "\n".join(pieces) or "(the server returned nothing)"
    return f"error: {joined}" if result.is_error else joined


def _declaration(server: str, tool) -> dict:
    """One server tool, as a model is given it.

    `input_schema` is JSON Schema and needs no adaptation - measured against
    the real SDK in cycle 1. The name carries the server so a collision with a
    built-in, or with another server's tool, cannot happen.
    """
    return {
        "type": "function",
        "function": {
            "name": qualified(server, tool.name),
            "description": tool.description or tool.title or tool.name,
            "parameters": tool.input_schema,
        },
    }


class Servers:
    """Every configured MCP server, and the one loop they all live on.

    Sessions open once, before the first prompt, and stay open for the whole
    run - so a tool called in a later turn does not restart anything, and a
    fresh run starts fresh servers.
    """

    def __init__(
        self,
        specs: tuple[ServerSpec, ...],
        start_timeout: float = START_TIMEOUT,
        call_timeout: float = CALL_TIMEOUT,
    ) -> None:
        self.specs = specs
        self.start_timeout = start_timeout
        self.call_timeout = call_timeout
        self.declarations: list[dict] = []
        self.connected: dict[str, int] = {}  # server -> tools declared
        self.failures: list[str] = []  # server -> why it did not start
        self._clients: dict[str, Client] = {}
        # qualified name -> (server, tool). Built when the tools are declared,
        # so routing is a lookup rather than a parse - see `split`.
        self._owner: dict[str, tuple[str, str]] = {}
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._run, daemon=True, name="mcp")
        self._ready = threading.Event()
        self._stop: asyncio.Event | None = None

    # -- lifetime ----------------------------------------------------------

    def start(self) -> None:
        """Open every session, before the first prompt, and wait for them."""
        if not self.specs:
            return
        self._thread.start()
        # The bound covers all of them together; a single slow server cannot
        # hold the prompt back indefinitely.
        self._ready.wait(self.start_timeout * len(self.specs) + self.start_timeout)

    def stop(self) -> None:
        """Close every session, and with it every subprocess.

        Called on the way out by every route axiom can leave by. A server that
        outlived axiom would be work happening that nobody is waiting for and
        nobody can see - the same reason #34 kills a command's whole tree.
        """
        if not self._thread.is_alive() or self._stop is None:
            return
        self._loop.call_soon_threadsafe(self._stop.set)
        self._thread.join(self.start_timeout)

    def _run(self) -> None:
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._serve())
        finally:
            self._loop.close()

    async def _serve(self) -> None:
        self._stop = asyncio.Event()
        # One stack holding every session open at once. Leaving it closes them
        # all, in reverse order, whatever happened in between.
        async with AsyncExitStack() as sessions:
            for spec in self.specs:
                await self._open(spec, sessions)
            self._ready.set()
            await self._stop.wait()

    async def _open(self, spec: ServerSpec, sessions: AsyncExitStack) -> None:
        """One server, or a recorded reason it is not there.

        A server that fails to start does not stop axiom: it starts without
        that server and says which one failed. Consistent with `tools.run()`
        returning failures rather than raising - a tool that cannot do its job
        is not a reason to end the session.
        """
        try:
            parameters = StdioServerParameters(
                command=spec.command,
                args=list(spec.args),
                env=dict(spec.env) or None,
            )
            # A server's stderr goes to axiom's by default, so one having a bad
            # day writes Python tracebacks into the middle of a conversation -
            # which `terminal.py` never sees and cannot format, and which must
            # never become a way for what the server was configured with to
            # reach the screen.
            #
            # `errlog` belongs to the transport rather than to the parameters,
            # and wants a text stream rather than a file descriptor - both
            # measured, because the obvious spellings are wrong.
            quiet = sessions.enter_context(
                open(os.devnull, "w", encoding="utf-8")  # noqa: SIM115
            )
            client = await asyncio.wait_for(
                sessions.enter_async_context(
                    Client(stdio_client(parameters, errlog=quiet))
                ),
                self.start_timeout,
            )
            listed = await asyncio.wait_for(client.list_tools(), self.start_timeout)
        except Exception as failed:  # noqa: BLE001
            # Whatever a third-party server does on the way down, it costs that
            # server and nothing else.
            self.failures.append(f"{spec.name}: {_reason(failed)}")
            return

        wanted = set(spec.tools)
        offered = {tool.name: tool for tool in listed.tools}
        for missing in sorted(wanted - set(offered)):
            self.failures.append(f"{spec.name}: no tool named {missing}")
        chosen = [
            tool for name, tool in offered.items() if not wanted or name in wanted
        ]
        self._clients[spec.name] = client
        for tool in chosen:
            self._owner[qualified(spec.name, tool.name)] = (spec.name, tool.name)
        self.declarations.extend(_declaration(spec.name, tool) for tool in chosen)
        self.connected[spec.name] = len(chosen)

    # -- calling -----------------------------------------------------------

    def owns(self, name: str) -> bool:
        """Whether this name is one a connected server actually declared."""
        return name in self._owner

    def run(self, name: str, arguments: dict) -> str:
        """Call a server's tool and return what the model should be told.

        Failures come back as text, never raised, for the same reason
        `tools.run()` does it: the model is the one that has to act on them.
        """
        if name not in self._owner:
            return f"error: there is no tool named {name!r}"
        server, tool = self._owner[name]
        client = self._clients[server]
        try:
            future = asyncio.run_coroutine_threadsafe(
                client.call_tool(tool, arguments), self._loop
            )
            return as_text(future.result(self.call_timeout))
        except TimeoutError:
            return f"error: {server} did not answer within {self.call_timeout:g} seconds"
        except Exception as failed:  # noqa: BLE001
            # A server that died mid-session fails its own tools with a reason,
            # and every other tool keeps working.
            return f"error: {server} could not run {tool} ({_reason(failed)})"


def _reason(failure: BaseException) -> str:
    """A failure as one line, never carrying what the server was configured with.

    A server that will not start often reports its own command line, and that
    command line may hold a value substituted from the environment. The type
    and the message are enough to act on; the rest is not ours to print.
    """
    text = str(failure) or type(failure).__name__
    return text.splitlines()[0][:200]

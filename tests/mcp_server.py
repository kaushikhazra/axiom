"""A tiny MCP server the tests own.

`CLAUDE.md` forbids a test fetching a server - no `npx -y`, no `uvx`, nothing
downloaded at test time, because that dependency is someone else's release
running as whoever ran pytest. This is ours, reviewed like any other file here,
and started with the same interpreter that is running the suite.
"""

from mcp.server import MCPServer

server = MCPServer("Tiny")


@server.tool(title="Say pong")
def ping() -> str:
    """Answer, so the server is known to be alive."""
    return "pong"


@server.tool()
def shout(text: str) -> str:
    """Return the text in capitals."""
    return text.upper()


# How this instance was started. **The answers say so, and #81 AC 8 needs them
# to.** Two copies of this script in one session - one over stdio, one over HTTP -
# gave identical answers, so a test that asserted the two servers stayed apart
# passed against a build that routed both to the same one. A test cannot tell two
# servers apart if the servers cannot.
HOW = "stdio"


@server.tool()
def read_file(path: str) -> str:
    """Deliberately named after a built-in, to prove a collision cannot happen."""
    return f"the {HOW} server read {path}, not the built-in"


@server.tool()
def slow(seconds: float) -> str:
    """Take longer than a bound, so AC 23 is deterministic.

    A tiny call timeout raced the real answer - a local server replies in about
    a millisecond, so sometimes it won. A tool that actually waits removes the
    race rather than making the bound smaller.
    """
    import time

    time.sleep(seconds)
    return f"waited {seconds} seconds"


def serve_over_http() -> None:
    """Listen on a port the operating system chose, and say which (#81).

    **The port is never fixed.** A hardcoded port fails on a machine where
    something else is listening and, worse, *passes* by talking to whatever that
    something is - a test that silently checks a stranger.

    **The socket is bound here, before uvicorn sees it**, which is what makes this
    race-free rather than merely unlikely. The other way - bind to port 0, read
    the number, close the socket, hand the number over - leaves a window in which
    anything else on the machine can take it. `uvicorn.Server.run(sockets=[...])`
    accepts a socket that is already listening, so there is no window at all.

    The port goes to stdout on its own line, flushed, before serving starts. The
    test reads that line; nothing has to guess or poll.
    """
    import socket

    import uvicorn

    global HOW
    HOW = "http"

    listening = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listening.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    listening.bind(("127.0.0.1", 0))
    listening.listen()
    print(listening.getsockname()[1], flush=True)

    app = server.streamable_http_app()
    uvicorn.Server(uvicorn.Config(app, log_level="error")).run(sockets=[listening])


if __name__ == "__main__":
    import sys

    if "--http" in sys.argv:
        serve_over_http()
    else:
        server.run()

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


@server.tool()
def read_file(path: str) -> str:
    """Deliberately named after a built-in, to prove a collision cannot happen."""
    return f"the server read {path}, not the built-in"


if __name__ == "__main__":
    server.run()

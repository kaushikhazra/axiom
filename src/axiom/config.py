"""Where a run gets its settings, and which source wins."""

import argparse
import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_HOST = "http://localhost:11434"
# There is deliberately no DEFAULT_MODEL. axiom used to name `qwen2.5:7b` here
# and take it on faith, which meant a host without that model got a confident
# startup line, a fabricated context and a fabricated tool verdict - because
# `model_info` and `supports_tools` both swallow the error and return
# None/False. A run's model now comes from the host, or from the user, and
# `models.choose` settles which. A default here would quietly become the
# fallback again the first time someone needed one.
DEFAULT_COMMAND_TIMEOUT = 30.0
DEFAULT_SEARCH_RESULTS = 5
DEFAULT_FETCH_TIMEOUT = 20.0
DEFAULT_PAGE_CHARACTERS = 20_000
DEFAULT_MCP_START_TIMEOUT = 30.0
DEFAULT_MCP_CALL_TIMEOUT = 60.0
OFF_VALUES = {"off", "0", "false", "no"}


@dataclass(frozen=True)
class Settings:
    """Resolved settings for one run.

    `debug_max_context` replaces the computed context outright rather than
    capping it - it exists to force small windows during testing.
    """

    host: str
    # What the user *named*, not what the run uses. None means they named
    # nothing, which is a real state now rather than an impossible one: it is
    # what sends a run to the list. The settled model lives in the chat loop,
    # because settling it needs the host's answer and this dataclass is built
    # before anything has been asked.
    model: str | None
    debug_max_context: int | None = None
    working_directory: str | None = None
    command_timeout: float = DEFAULT_COMMAND_TIMEOUT
    tools_enabled: bool = True
    search_results: int = DEFAULT_SEARCH_RESULTS
    fetch_timeout: float = DEFAULT_FETCH_TIMEOUT
    page_characters: int = DEFAULT_PAGE_CHARACTERS
    web_enabled: bool = True
    mcp_start_timeout: float = DEFAULT_MCP_START_TIMEOUT
    mcp_call_timeout: float = DEFAULT_MCP_CALL_TIMEOUT
    mcp_servers: tuple["ServerSpec", ...] = ()
    # Named one by one rather than counted: a variable the user has not set is
    # fixed by setting that variable, and a count does not say which.
    mcp_problems: tuple[str, ...] = ()


DEFAULT_MCP_FILE = Path(".axiom") / "mcp.json"

# `${NAME}`, so the file holds the name of a secret and never its value - which
# is what makes it safe to commit. Deliberately not `$NAME`: a bare dollar is
# ordinary in a command line, and treating it as a reference would rewrite
# arguments nobody meant as references.
REFERENCE = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")


@dataclass(frozen=True)
class ServerSpec:
    """One MCP server, as the user asked for it and as it will be started."""

    name: str
    command: str
    args: tuple[str, ...] = ()
    env: dict[str, str] = field(default_factory=dict)
    # Only the tools named here are declared. Empty means all of them.
    tools: tuple[str, ...] = ()


def _substituted(value: str, missing: list[str]) -> str:
    """`${NAME}` replaced from the environment, and what was not set.

    An unset variable becomes the empty string rather than the literal
    `${NAME}`: passing the reference through would hand a server the text of
    the placeholder as though it were a token, and it would fail somewhere
    further away with something less useful to say.
    """

    def replace(match: re.Match) -> str:
        name = match.group(1)
        found = os.environ.get(name)
        if found is None:
            missing.append(name)
            return ""
        return found

    return REFERENCE.sub(replace, value)


def read_servers(path: Path) -> tuple[tuple[ServerSpec, ...], tuple[str, ...]]:
    """The servers a project asks for, and anything wrong with the asking.

    Problems are returned rather than raised. A bad entry costs that server,
    not the session - the same reason `tools.run()` returns failures as text.
    """
    if not path.is_file():
        return (), ()

    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as unreadable:
        return (), (f"{path} could not be read ({unreadable})",)

    entries = document.get("mcpServers") if isinstance(document, dict) else None
    if not isinstance(entries, dict):
        return (), (f"{path} has no mcpServers section",)

    servers: list[ServerSpec] = []
    problems: list[str] = []
    for name, entry in entries.items():
        if not isinstance(entry, dict) or not entry.get("command"):
            problems.append(f"{name} names no command")
            continue
        missing: list[str] = []
        command = _substituted(str(entry["command"]), missing)
        args = tuple(_substituted(str(a), missing) for a in entry.get("args") or ())
        env = {
            key: _substituted(str(value), missing)
            for key, value in (entry.get("env") or {}).items()
        }
        tools = tuple(str(t) for t in entry.get("tools") or ())
        for name_of_variable in missing:
            problems.append(f"{name} wants ${{{name_of_variable}}}, which is not set")
        servers.append(ServerSpec(name, command, args, env, tools))
    return tuple(servers), tuple(problems)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="axiom", description="Chat with a local Ollama model."
    )
    parser.add_argument(
        "--host",
        default=os.environ.get("AXIOM_HOST", DEFAULT_HOST),
        help=f"Ollama host. Overrides $AXIOM_HOST. Default: {DEFAULT_HOST}",
    )
    parser.add_argument(
        "--model",
        default=os.environ.get("AXIOM_MODEL"),
        help=(
            "Model to chat with. Overrides $AXIOM_MODEL. With neither set, "
            "axiom lists the models installed on the host and asks - or uses "
            "your last choice there when input is not a terminal"
        ),
    )
    parser.add_argument(
        "--working-directory",
        default=os.environ.get("AXIOM_WORKING_DIRECTORY"),
        help=(
            "Directory tools act in. Overrides $AXIOM_WORKING_DIRECTORY. "
            "Default: where axiom was started"
        ),
    )
    parser.add_argument(
        "--command-timeout",
        type=float,
        default=float(os.environ.get("AXIOM_COMMAND_TIMEOUT", DEFAULT_COMMAND_TIMEOUT)),
        help=(
            "Seconds a command may run before it is stopped. Overrides "
            f"$AXIOM_COMMAND_TIMEOUT. Default: {DEFAULT_COMMAND_TIMEOUT:g}"
        ),
    )
    parser.add_argument(
        "--no-tools",
        action="store_true",
        default=os.environ.get("AXIOM_TOOLS", "").lower() in OFF_VALUES,
        help="Chat without tools. Overrides $AXIOM_TOOLS. Default: tools on",
    )
    parser.add_argument(
        "--search-results",
        type=int,
        default=int(os.environ.get("AXIOM_SEARCH_RESULTS", DEFAULT_SEARCH_RESULTS)),
        help=(
            "Results a search returns. Overrides $AXIOM_SEARCH_RESULTS. "
            f"Default: {DEFAULT_SEARCH_RESULTS}"
        ),
    )
    parser.add_argument(
        "--fetch-timeout",
        type=float,
        default=float(os.environ.get("AXIOM_FETCH_TIMEOUT", DEFAULT_FETCH_TIMEOUT)),
        help=(
            "Seconds a page fetch may take. Overrides $AXIOM_FETCH_TIMEOUT. "
            f"Default: {DEFAULT_FETCH_TIMEOUT:g}"
        ),
    )
    parser.add_argument(
        "--page-characters",
        type=int,
        default=int(os.environ.get("AXIOM_PAGE_CHARACTERS", DEFAULT_PAGE_CHARACTERS)),
        help=(
            "Characters of a page kept. Overrides $AXIOM_PAGE_CHARACTERS. "
            f"Default: {DEFAULT_PAGE_CHARACTERS}"
        ),
    )
    parser.add_argument(
        "--no-web",
        action="store_true",
        default=os.environ.get("AXIOM_WEB", "").lower() in OFF_VALUES,
        help=(
            "Chat without searching or fetching, keeping the other tools. "
            "Overrides $AXIOM_WEB. Default: web on"
        ),
    )
    parser.add_argument(
        "--no-mcp",
        action="store_true",
        default=os.environ.get("AXIOM_MCP", "").lower() in OFF_VALUES,
        help=(
            "Chat without any MCP server, whatever the config file says. "
            "Overrides $AXIOM_MCP. Default: MCP on"
        ),
    )
    parser.add_argument(
        "--mcp-start-timeout",
        type=float,
        default=float(
            os.environ.get("AXIOM_MCP_START_TIMEOUT", DEFAULT_MCP_START_TIMEOUT)
        ),
        help=(
            "Seconds a server may take to start. Overrides "
            f"$AXIOM_MCP_START_TIMEOUT. Default: {DEFAULT_MCP_START_TIMEOUT:g}"
        ),
    )
    parser.add_argument(
        "--mcp-call-timeout",
        type=float,
        default=float(
            os.environ.get("AXIOM_MCP_CALL_TIMEOUT", DEFAULT_MCP_CALL_TIMEOUT)
        ),
        help=(
            "Seconds a server's tool may take. Overrides $AXIOM_MCP_CALL_TIMEOUT. "
            f"Default: {DEFAULT_MCP_CALL_TIMEOUT:g}"
        ),
    )
    parser.add_argument(
        "--mcp-file",
        default=os.environ.get("AXIOM_MCP_FILE"),
        help=(
            "Where the MCP server config lives. Overrides $AXIOM_MCP_FILE. "
            f"Default: {DEFAULT_MCP_FILE}"
        ),
    )
    return parser.parse_args(argv)


def resolve(argv: list[str] | None = None) -> Settings:
    """Settings for this run: command line, else environment, else default."""
    args = parse_args(argv)
    override = os.environ.get("AXIOM_DEBUG_MAX_CONTEXT")
    # A blank model is nobody naming a model. `AXIOM_MODEL=` is how a shell
    # unsets it in practice, and `--model "  "` is a slip - neither is a
    # request for a model whose name is empty. Without this the empty string
    # is carried as a name: it happens to behave correctly because "" is
    # falsy, but whitespace is truthy and produced a message with a hole in
    # it - "axiom:     is not installed on http://localhost:11434".
    named = (args.model or "").strip() or None
    return Settings(
        host=args.host,
        model=named,
        debug_max_context=int(override) if override is not None else None,
        working_directory=args.working_directory,
        command_timeout=args.command_timeout,
        tools_enabled=not args.no_tools,
        search_results=args.search_results,
        fetch_timeout=args.fetch_timeout,
        page_characters=args.page_characters,
        # --no-tools takes everything, web included: switching off tools and
        # leaving the web on would be the clever answer, not the obvious one.
        web_enabled=not args.no_web and not args.no_tools,
        # --no-tools takes MCP with it, the same way it already takes the web:
        # switching off tools and leaving someone else's tools on would be the
        # clever answer, not the obvious one.
        **_mcp(args),
    )


def _mcp(args: argparse.Namespace) -> dict:
    """The MCP half of the settings, read only when it is wanted."""
    timeouts = {
        "mcp_start_timeout": args.mcp_start_timeout,
        "mcp_call_timeout": args.mcp_call_timeout,
    }
    if args.no_mcp or args.no_tools:
        # The bounds are still resolved, so what the user asked for is what
        # `Settings` reports whether or not any server ends up using them.
        return {"mcp_servers": (), "mcp_problems": (), **timeouts}
    path = Path(args.mcp_file) if args.mcp_file else DEFAULT_MCP_FILE
    servers, problems = read_servers(path)
    return {
        "mcp_servers": servers,
        "mcp_problems": problems,
        "mcp_start_timeout": args.mcp_start_timeout,
        "mcp_call_timeout": args.mcp_call_timeout,
    }

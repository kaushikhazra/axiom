"""Where a run gets its settings, and which source wins."""

import argparse
import os
from dataclasses import dataclass

DEFAULT_HOST = "http://localhost:11434"
DEFAULT_MODEL = "qwen2.5:7b"
DEFAULT_COMMAND_TIMEOUT = 30.0
DEFAULT_SEARCH_RESULTS = 5
DEFAULT_FETCH_TIMEOUT = 20.0
DEFAULT_PAGE_CHARACTERS = 20_000
OFF_VALUES = {"off", "0", "false", "no"}


@dataclass(frozen=True)
class Settings:
    """Resolved settings for one run.

    `debug_max_context` replaces the computed context outright rather than
    capping it - it exists to force small windows during testing.
    """

    host: str
    model: str
    debug_max_context: int | None = None
    working_directory: str | None = None
    command_timeout: float = DEFAULT_COMMAND_TIMEOUT
    tools_enabled: bool = True
    search_results: int = DEFAULT_SEARCH_RESULTS
    fetch_timeout: float = DEFAULT_FETCH_TIMEOUT
    page_characters: int = DEFAULT_PAGE_CHARACTERS
    web_enabled: bool = True


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
        default=os.environ.get("AXIOM_MODEL", DEFAULT_MODEL),
        help=f"Model to chat with. Overrides $AXIOM_MODEL. Default: {DEFAULT_MODEL}",
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
    return parser.parse_args(argv)


def resolve(argv: list[str] | None = None) -> Settings:
    """Settings for this run: command line, else environment, else default."""
    args = parse_args(argv)
    override = os.environ.get("AXIOM_DEBUG_MAX_CONTEXT")
    return Settings(
        host=args.host,
        model=args.model,
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
    )

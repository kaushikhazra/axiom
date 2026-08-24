"""Where a run gets its settings, and which source wins."""

import argparse
import os
from dataclasses import dataclass

DEFAULT_HOST = "http://localhost:11434"
DEFAULT_MODEL = "qwen2.5:7b"


@dataclass(frozen=True)
class Settings:
    """Resolved settings for one run.

    `debug_max_context` is the AXIOM_DEBUG_MAX_CONTEXT override, which replaces
    the computed context outright rather than capping it - it exists to force
    small windows during testing, so it has to be able to go below what the
    model and the machine would allow.
    """

    host: str
    model: str
    debug_max_context: int | None = None


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
    return parser.parse_args(argv)


def resolve(argv: list[str] | None = None) -> Settings:
    """Settings for this run: command line, else environment, else default."""
    args = parse_args(argv)
    override = os.environ.get("AXIOM_DEBUG_MAX_CONTEXT")
    return Settings(
        host=args.host,
        model=args.model,
        debug_max_context=int(override) if override is not None else None,
    )

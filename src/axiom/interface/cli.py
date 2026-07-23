"""
CLI entry point — pure I/O.

Reads user input, calls agent.run(), prints response.
Never imports loop, adapter, persona, or observability directly.
Imports axiom.agent only.
"""

from __future__ import annotations

import argparse
import sys

from axiom.agent import Agent


def main() -> None:
    """Parse args, run one agent turn, print the response."""
    parser = argparse.ArgumentParser(
        prog="axiom-cli",
        description="Axiom — agentic assistant (M1 walking skeleton)",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable DEBUG logging to stderr (latency, intent parse, adapter errors)",
    )
    parser.add_argument(
        "--provider",
        choices=["claude", "local"],
        default="claude",
        help="Provider adapter: 'claude' (default, cloud) or 'local' (Ollama via LiteLLM)",
    )
    parser.add_argument(
        "--ollama-host",
        default=None,
        help=(
            "Ollama API base URL for --provider local (e.g. http://192.168.0.235:11434). "
            "Defaults to http://localhost:11434 when omitted."
        ),
    )
    parser.add_argument(
        "--observe",
        action="store_true",
        default=False,
        help=(
            "Enable M2 observability: write a JSONL phase-span trace to "
            "~/.axiom/traces/<run_id>.jsonl and print the path to stderr."
        ),
    )
    parser.add_argument(
        "input",
        nargs="?",
        help="User input (reads from stdin if omitted)",
    )
    args = parser.parse_args()

    if args.input is not None:
        user_input = args.input
    else:
        print("Axiom > ", end="", flush=True)
        user_input = sys.stdin.readline().strip()

    if not user_input:
        print("No input provided.", file=sys.stderr)
        sys.exit(1)

    agent = Agent(
        debug=args.debug,
        provider=args.provider,
        observe=args.observe,
        ollama_host=args.ollama_host,
    )

    if args.observe and agent.trace_path is not None:
        print(f"[axiom] trace → {agent.trace_path}", file=sys.stderr)

    response = agent.run(user_input)

    if response:
        print(response)


if __name__ == "__main__":
    main()

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

    agent = Agent(debug=args.debug)
    response = agent.run(user_input)

    if response:
        print(response)


if __name__ == "__main__":
    main()

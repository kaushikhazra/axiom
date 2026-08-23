"""A terminal chat with a local Ollama model."""

import argparse
import os
import sys

import httpx
import ollama

DEFAULT_HOST = "http://localhost:11434"
DEFAULT_MODEL = "qwen2.5:7b"
EXIT_COMMANDS = {"/exit", "/quit"}


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


def main() -> None:
    args = parse_args()
    client = ollama.Client(host=args.host)
    print(f"axiom: {args.model} at {args.host}")

    messages: list[dict[str, str]] = []

    while True:
        try:
            line = input("> ").strip()
        except EOFError:
            print()
            return

        if not line:
            continue
        if line in EXIT_COMMANDS:
            return

        messages.append({"role": "user", "content": line})
        try:
            reply = (
                client.chat(model=args.model, messages=messages).message.content or ""
            )
        except ollama.ResponseError as error:
            messages.pop()
            print(f"error: {error}", file=sys.stderr)
            continue
        except (ConnectionError, httpx.HTTPError) as error:
            # ollama turns a refused *connect* into ConnectionError, but a
            # connection dropped mid-request surfaces as a raw httpx error.
            messages.pop()
            print(
                f"error: cannot reach Ollama at {args.host} ({error})", file=sys.stderr
            )
            continue

        print(reply)
        messages.append({"role": "assistant", "content": reply})

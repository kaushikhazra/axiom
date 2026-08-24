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


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    client = ollama.Client(host=args.host)
    print(f"axiom: {args.model} at {args.host}")

    messages: list[dict[str, str]] = []

    while True:
        try:
            line = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            # Ctrl-C at an idle prompt means leave, same as Ctrl-D.
            print()
            return

        if not line:
            continue
        if line in EXIT_COMMANDS:
            return

        messages.append({"role": "user", "content": line})
        reply = ""
        try:
            for chunk in client.chat(model=args.model, messages=messages, stream=True):
                piece = chunk.message.content or ""
                reply += piece
                print(piece, end="", flush=True)
        except KeyboardInterrupt:
            # Ctrl-C mid-generation cancels this reply only. The session lives,
            # and the half-finished answer does not become history.
            messages.pop()
            print(file=sys.stderr)
            print(f"cancelled after {len(reply)} characters", file=sys.stderr)
            continue
        except ollama.ResponseError as error:
            messages.pop()
            print(f"\nerror: {error}" if reply else f"error: {error}", file=sys.stderr)
            continue
        except (ConnectionError, httpx.HTTPError) as error:
            # ollama turns a refused *connect* into ConnectionError, but a
            # connection dropped mid-request surfaces as a raw httpx error.
            messages.pop()
            if reply:
                # Part of a reply is already on screen. Say so, or the user
                # reads a fragment as though it were the whole answer.
                print(file=sys.stderr)
                print(
                    f"error: reply cut off after {len(reply)} characters "
                    f"- lost connection to {args.host} ({error})",
                    file=sys.stderr,
                )
            else:
                print(
                    f"error: cannot reach Ollama at {args.host} ({error})",
                    file=sys.stderr,
                )
            continue

        print()
        messages.append({"role": "assistant", "content": reply})

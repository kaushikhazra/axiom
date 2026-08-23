"""A terminal chat with a local Ollama model."""

import ollama

HOST = "http://localhost:11434"
MODEL = "qwen2.5:7b"
EXIT_COMMANDS = {"/exit", "/quit"}


def main() -> None:
    client = ollama.Client(host=HOST)
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
        reply = client.chat(model=MODEL, messages=messages).message.content or ""
        print(reply)
        messages.append({"role": "assistant", "content": reply})

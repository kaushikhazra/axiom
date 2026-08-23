"""A terminal chat with a local Ollama model."""

import ollama

HOST = "http://localhost:11434"
MODEL = "qwen2.5:7b"


def main() -> None:
    client = ollama.Client(host=HOST)
    message = input("> ")
    reply = client.chat(model=MODEL, messages=[{"role": "user", "content": message}])
    print(reply.message.content)

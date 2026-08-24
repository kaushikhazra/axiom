"""A terminal chat with a local Ollama model."""

import argparse
import os
import sys

import httpx
import ollama
import psutil

DEFAULT_HOST = "http://localhost:11434"
DEFAULT_MODEL = "qwen2.5:7b"
EXIT_COMMANDS = {"/exit", "/quit"}
SAFE_MEMORY_FRACTION = 0.70
KV_CACHE_BYTES_PER_VALUE = 2  # Ollama's default KV cache precision (f16)


def model_info_for(client: ollama.Client, model: str) -> dict | None:
    """The model's raw model_info, or None if Ollama can't be reached or asked."""
    try:
        return client.show(model).modelinfo or {}
    except (ollama.ResponseError, ConnectionError, httpx.HTTPError):
        return None


def _find(info: dict, suffix: str):
    for key, value in info.items():
        if key.endswith(suffix):
            return value
    return None


def model_max_context(info: dict) -> int | None:
    """The model's own reported max context length, or None if it doesn't say."""
    value = _find(info, ".context_length")
    return int(value) if value is not None else None


def kv_cache_bytes_per_token(info: dict) -> int | None:
    """Bytes of KV cache one token of context costs, at Ollama's default f16 cache.

    2 (K+V) x layers x kv_heads x head_dim x bytes_per_value. Prefers the model's
    own reported key_length for head_dim over embedding_length / head_count - they
    differ for architectures with shared or sliding-window attention (e.g. gemma4,
    where key_length=512 but embedding_length/head_count=192). Overestimating this
    only makes the resulting token budget more conservative, never less safe.
    """
    num_layers = _find(info, ".block_count")
    num_kv_heads = _find(info, ".attention.head_count_kv")
    head_dim = _find(info, ".attention.key_length")
    if head_dim is None:
        embedding_length = _find(info, ".embedding_length")
        head_count = _find(info, ".attention.head_count")
        if not embedding_length or not head_count:
            return None
        head_dim = embedding_length / head_count
    if not num_layers or not num_kv_heads:
        return None
    return int(2 * num_layers * num_kv_heads * head_dim * KV_CACHE_BYTES_PER_VALUE)


def available_memory() -> int | None:
    """Bytes of memory currently free on this machine, or None if unknown."""
    try:
        return psutil.virtual_memory().available
    except Exception:
        return None


def memory_safe_context(info: dict, available_bytes: int | None) -> int | None:
    """How many tokens of context fit in SAFE_MEMORY_FRACTION of available memory."""
    if available_bytes is None:
        return None
    bytes_per_token = kv_cache_bytes_per_token(info)
    if not bytes_per_token:
        return None
    budget_bytes = int(available_bytes * SAFE_MEMORY_FRACTION)
    return budget_bytes // bytes_per_token


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

    info = model_info_for(client, args.model)
    max_context = model_max_context(info) if info else None
    safe_context = memory_safe_context(info, available_memory()) if info else None
    candidates = [c for c in (max_context, safe_context) if c is not None]
    effective_context = min(candidates) if candidates else None

    chat_options = (
        {"num_ctx": effective_context} if effective_context is not None else None
    )
    context_note = (
        f"{effective_context} tokens"
        if effective_context is not None
        else "Ollama default"
    )
    print(f"axiom: {args.model} at {args.host} (context: {context_note})")

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
            for chunk in client.chat(
                model=args.model, messages=messages, stream=True, options=chat_options
            ):
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

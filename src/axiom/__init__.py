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


COMPACTION_INSTRUCTION = (
    "Summarize the conversation below concisely. Preserve every specific "
    "fact, name, and number mentioned - a reader must be able to answer "
    "questions about it from your summary alone, without the original "
    "text.\n\n"
)


def compact(client: ollama.Client, model: str, pairs: list[dict[str, str]]) -> str:
    """Summarize a run of {role, content} messages into shorter text.

    Proven standalone in cycle 1: a real fact survives (recalled correctly
    from the summary alone) while the text genuinely shrinks. Not wired into
    the chat loop yet.
    """
    transcript = "\n".join(f"{m['role']}: {m['content']}" for m in pairs)
    reply = client.chat(
        model=model,
        messages=[{"role": "user", "content": COMPACTION_INSTRUCTION + transcript}],
    )
    return reply.message.content or ""


COMPACTION_TRIGGER_FRACTION = 0.90
KEPT_PAIRS_LADDER = (10, 5, 2, 0)
CHARS_PER_TOKEN_ESTIMATE = 4  # rough proxy for a hypothetical, not-yet-sent payload


def estimated_tokens(messages: list[dict[str, str]]) -> int:
    """A rough size estimate for history that hasn't been sent yet - no real
    prompt_eval_count exists for a hypothetical payload. Only used to choose
    an escalation level; the real trigger check uses the actual last
    prompt_eval_count + eval_count instead.
    """
    chars = sum(len(m["content"]) for m in messages)
    return chars // CHARS_PER_TOKEN_ESTIMATE


def compacted_history(
    client: ollama.Client, model: str, messages: list[dict[str, str]], kept_pairs: int
) -> list[dict[str, str]]:
    """messages with everything older than the last kept_pairs pairs replaced
    by one system-role summary. kept_pairs=0 compacts everything. Returns
    messages unchanged (same object) if there is nothing older to compact.
    """
    kept_count = kept_pairs * 2
    older = messages if kept_count == 0 else messages[:-kept_count]
    kept = [] if kept_count == 0 else messages[-kept_count:]
    if not older:
        return messages
    summary = compact(client, model, older)
    return [
        {"role": "system", "content": f"Summary of earlier conversation: {summary}"},
        *kept,
    ]


def maybe_compact(
    client: ollama.Client,
    model: str,
    messages: list[dict[str, str]],
    running_usage: int | None,
    effective_context: int | None,
) -> tuple[list[dict[str, str]], int | None]:
    """(possibly-compacted messages, the kept_pairs level used - None if untouched).

    Triggers on the REAL running usage from the last completed turn. Escalation
    levels are chosen with the character-based estimate - there is no real
    count for a payload not yet sent.
    """
    if running_usage is None or effective_context is None:
        return messages, None
    if running_usage < effective_context * COMPACTION_TRIGGER_FRACTION:
        return messages, None

    for kept_pairs in KEPT_PAIRS_LADDER:
        candidate = compacted_history(client, model, messages, kept_pairs)
        if candidate is messages:
            continue  # nothing older than this level - try a smaller kept window
        if (
            kept_pairs == 0
            or estimated_tokens(candidate)
            < effective_context * COMPACTION_TRIGGER_FRACTION
        ):
            return candidate, kept_pairs
    return messages, None


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
    running_usage: int | None = None  # real prompt_eval_count + eval_count, last turn

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

        messages, kept_pairs = maybe_compact(
            client, args.model, messages, running_usage, effective_context
        )
        if kept_pairs is not None:
            level = (
                "everything" if kept_pairs == 0 else f"keeping the last {kept_pairs}"
            )
            print(f"axiom: compacting older history ({level})")

        messages.append({"role": "user", "content": line})
        reply = ""
        last_chunk = None
        try:
            for chunk in client.chat(
                model=args.model, messages=messages, stream=True, options=chat_options
            ):
                piece = chunk.message.content or ""
                reply += piece
                print(piece, end="", flush=True)
                last_chunk = chunk
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
        if last_chunk is not None:
            running_usage = (last_chunk.prompt_eval_count or 0) + (
                last_chunk.eval_count or 0
            )

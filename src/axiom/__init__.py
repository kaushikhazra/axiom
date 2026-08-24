"""A terminal chat with a local Ollama model."""

import sys

import httpx
import ollama

from . import config, context

EXIT_COMMANDS = {"/exit", "/quit"}


def model_info_for(client: ollama.Client, model: str) -> dict | None:
    """The model's raw model_info, or None if Ollama can't be reached or asked."""
    try:
        return client.show(model).modelinfo or {}
    except (ollama.ResponseError, ConnectionError, httpx.HTTPError):
        return None


COMPACTION_INSTRUCTION = (
    "Extract every distinct fact, stated preference, name, and number from "
    "the conversation below as a bulleted list - one bullet per fact, in "
    "the order it was mentioned. Do not write a narrative summary. Do not "
    "judge some facts as more important than others: a brief, early "
    "statement (e.g. a stated preference) is exactly as important to keep "
    "as a later, longer topic. Omit nothing a reader would need to answer "
    "a question about anything mentioned below.\n\n"
)


def compact(client: ollama.Client, model: str, pairs: list[dict[str, str]]) -> str:
    """Summarize a run of {role, content} messages into shorter text."""
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

    Never re-summarizes an existing summary: if `older` already starts with
    a prior pass's system-role summary, that text is carried forward
    verbatim and only the genuinely new messages since then are compacted.
    Re-summarizing an already-compacted summary alongside newer turns was
    found, live, to silently drop facts the first pass had preserved.
    """
    kept_count = kept_pairs * 2
    older = messages if kept_count == 0 else messages[:-kept_count]
    kept = [] if kept_count == 0 else messages[-kept_count:]
    if not older:
        return messages

    if older[0]["role"] == "system":
        prior_summary = older[0]["content"]
        new_older = older[1:]
        new_facts = compact(client, model, new_older) if new_older else ""
        content = prior_summary + (f"\n{new_facts}" if new_facts else "")
    else:
        content = f"Summary of earlier conversation: {compact(client, model, older)}"

    return [{"role": "system", "content": content}, *kept]


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


def main(argv: list[str] | None = None) -> None:
    settings = config.resolve(argv)
    client = ollama.Client(host=settings.host)

    effective_context = context.effective_context(
        model_info_for(client, settings.model)
    )

    context_note_suffix = ""
    if settings.debug_max_context is not None:
        effective_context = settings.debug_max_context
        context_note_suffix = ", debug override"

    chat_options = (
        {"num_ctx": effective_context} if effective_context is not None else None
    )
    context_note = (
        f"{effective_context} tokens{context_note_suffix}"
        if effective_context is not None
        else "Ollama default"
    )
    print(f"axiom: {settings.model} at {settings.host} (context: {context_note})")

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
            client, settings.model, messages, running_usage, effective_context
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
                model=settings.model,
                messages=messages,
                stream=True,
                options=chat_options,
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
                    f"- lost connection to {settings.host} ({error})",
                    file=sys.stderr,
                )
            else:
                print(
                    f"error: cannot reach Ollama at {settings.host} ({error})",
                    file=sys.stderr,
                )
            continue

        print()
        messages.append({"role": "assistant", "content": reply})
        if last_chunk is not None:
            running_usage = (last_chunk.prompt_eval_count or 0) + (
                last_chunk.eval_count or 0
            )

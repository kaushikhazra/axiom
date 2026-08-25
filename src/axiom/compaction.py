"""When history is compacted, and how much of it survives."""

from .backend import ModelBackend

COMPACTION_INSTRUCTION = (
    "Extract every distinct fact, stated preference, name, and number from "
    "the conversation below as a bulleted list - one bullet per fact, in "
    "the order it was mentioned. Do not write a narrative summary. Do not "
    "judge some facts as more important than others: a brief, early "
    "statement (e.g. a stated preference) is exactly as important to keep "
    "as a later, longer topic. Omit nothing a reader would need to answer "
    "a question about anything mentioned below.\n\n"
)

COMPACTION_TRIGGER_FRACTION = 0.90
KEPT_PAIRS_LADDER = (10, 5, 2, 0)
CHARS_PER_TOKEN_ESTIMATE = 4  # rough proxy for a hypothetical, not-yet-sent payload

# Measured against real prompt_eval_count: the character estimate underestimates
# in every sample, worst at 3.13 chars per token for code. For a check whose job
# is to be safe, the direction that matters is the one that says a payload fits
# when it does not - so the safety check divides by three, not four.
SAFE_CHARS_PER_TOKEN = 3

# Ollama truncates an oversized prompt without raising, and reports what it
# actually evaluated. Measured: ~4,100 estimated tokens sent came back as 258,
# a ratio of 0.06; a normal turn was 630 reported against 906 estimated, 0.70.
# The threshold sits between with room on both sides.
TRUNCATION_RATIO = 0.35

# And a floor, because the ratio alone is noise on a small payload: a five-token
# estimate answered with one reported token is rounding, not a cut conversation.
# Truncation only happens near the window, so the shortfall is always large.
MIN_TRUNCATION_SHORTFALL = 100


def _as_line(message: dict) -> str:
    """One message, as the summarizer sees it.

    A message carrying tool calls has no content of its own, so rendering only
    content would show a blank line and lose what was asked for. The result
    that follows would then be a fact with no question - "the file said X"
    with no record of which file.
    """
    calls = message.get("tool_calls")
    if calls:
        asked = ", ".join(
            f"{call['function']['name']}({call['function']['arguments']})"
            for call in calls
        )
        return f"{message['role']}: called {asked}"
    return f"{message['role']}: {message['content']}"


def compact(backend: ModelBackend, model: str, pairs: list[dict[str, str]]) -> str:
    """Summarize a run of messages into shorter text."""
    transcript = "\n".join(_as_line(m) for m in pairs)
    summary = backend.complete(
        model, [{"role": "user", "content": COMPACTION_INSTRUCTION + transcript}]
    )
    # A backend that answers with nothing yields an empty summary, never None -
    # the caller concatenates this straight into history.
    return summary or ""


def estimated_tokens(messages: list[dict[str, str]]) -> int:
    """A rough size estimate for history that hasn't been sent yet - no real
    prompt_eval_count exists for a hypothetical payload. Only used to choose
    an escalation level; the real trigger check uses the actual last
    prompt_eval_count + eval_count instead.
    """
    chars = sum(len(m["content"]) for m in messages)
    return chars // CHARS_PER_TOKEN_ESTIMATE


def too_large(
    messages: list[dict[str, str]], effective_context: int | None
) -> int | None:
    """How many tokens the assembled payload is over the context, or None if it fits.

    Uses the conservative divisor. This is the check that decides whether to
    send at all, and being wrong optimistically means an answer built on a
    prompt the model never fully saw.
    """
    if effective_context is None:
        return None
    chars = sum(len(message.get("content") or "") for message in messages)
    tokens = chars // SAFE_CHARS_PER_TOKEN
    return tokens - effective_context if tokens > effective_context else None


def looks_truncated(estimated: int, reported: int | None) -> bool:
    """Whether the model evidently saw far less than was sent.

    There is no error to catch - Ollama accepts an oversized prompt, cuts it,
    and answers confidently from the fragment. The only signal is the count of
    what it actually evaluated coming back far short of what went out.
    """
    if not reported or estimated <= 0:
        return False
    if estimated - reported < MIN_TRUNCATION_SHORTFALL:
        return False
    return reported < estimated * TRUNCATION_RATIO


def _turn_boundary(messages: list[dict[str, str]], index: int) -> int:
    """The first place at or after `index` where a turn starts.

    A turn is not always two messages. One that used tools runs user ->
    assistant-with-calls -> tool -> assistant, and cutting inside it would keep
    a tool result whose call had been summarized away - a result for a request
    the model never made. Snapping forward rather than back keeps at most what
    was asked for, so a compaction candidate never grows.
    """
    for position in range(index, len(messages)):
        if messages[position]["role"] == "user":
            return position
    return len(messages)


def compacted_history(
    backend: ModelBackend,
    model: str,
    messages: list[dict[str, str]],
    kept_pairs: int,
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
    wanted = len(messages) - kept_count
    if kept_count == 0:
        split = len(messages)
    elif wanted <= 0:
        # The kept window already covers everything. Snapping forward here
        # would find a boundary past a leading summary and compact a history
        # that has nothing older in it.
        split = 0
    else:
        split = _turn_boundary(messages, wanted)
    older, kept = messages[:split], messages[split:]
    if not older:
        return messages

    if older[0]["role"] == "system":
        prior_summary = older[0]["content"]
        new_older = older[1:]
        new_facts = compact(backend, model, new_older) if new_older else ""
        content = prior_summary + (f"\n{new_facts}" if new_facts else "")
    else:
        content = f"Summary of earlier conversation: {compact(backend, model, older)}"

    return [{"role": "system", "content": content}, *kept]


def maybe_compact(
    backend: ModelBackend,
    model: str,
    messages: list[dict[str, str]],
    running_usage: int | None,
    effective_context: int | None,
) -> tuple[list[dict[str, str]], int | None, bool]:
    """(possibly-compacted messages, the kept_pairs level used - None if untouched).

    Triggers on the REAL running usage from the last completed turn. Escalation
    levels are chosen with the character-based estimate - there is no real
    count for a payload not yet sent.
    """
    if running_usage is None or effective_context is None:
        return messages, None, False
    if running_usage < effective_context * COMPACTION_TRIGGER_FRACTION:
        return messages, None, False

    for kept_pairs in KEPT_PAIRS_LADDER:
        candidate = compacted_history(backend, model, messages, kept_pairs)
        if candidate is messages:
            continue  # nothing older than this level - try a smaller kept window
        if (
            kept_pairs == 0
            or estimated_tokens(candidate)
            < effective_context * COMPACTION_TRIGGER_FRACTION
        ):
            return candidate, kept_pairs, False
    return messages, None, False

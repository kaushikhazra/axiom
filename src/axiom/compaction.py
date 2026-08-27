"""When history is compacted, and how much of it survives."""

from .backend import ModelBackend

# Three paragraphs, and the order matters. What to extract, then what does not
# belong, then what must not be dropped - so the "omit nothing" rule reads as a
# floor on the conversation's own record rather than a licence to keep
# everything the model happened to say.
#
# The middle paragraph is #62. Without it the instruction asks for "every fact
# from the conversation", and a model that explained what an MMORPG stands for
# *did* say that during the conversation - so it belongs, by this instruction.
# Measured before the change: eight bullets from a short talk, three of them
# general knowledge, in a store bounded at half the window.
#
# It is deliberately about **provenance, not importance**, and says so. The
# third paragraph forbids ranking facts by importance, and #32 put it there
# after oldest-first dropping lost "my cat is called Biscuit" from turn one.
# Conflating the two axes would re-open that.
COMPACTION_INSTRUCTION = (
    "Extract every distinct fact, stated preference, name, and number from "
    "the conversation below as a bulleted list - one bullet per fact, in "
    "the order it was mentioned. Do not write a narrative summary.\n\n"
    "Then remove any bullet that would still be true if this conversation had "
    "never happened. Definitions, dates, public facts and anything you "
    "explained are all still true without it - drop them, because they can be "
    "asked for again. What the user said, asked for, chose or decided is only "
    "true because of this conversation - keep all of it, and keep anything a "
    "tool found. This is about where a fact came from, not about how "
    "important it is.\n\n"
    "Do not judge some facts as more important than others: a brief, early "
    "statement (e.g. a stated preference) is exactly as important to keep "
    "as a later, longer topic. Omit nothing from the conversation's own "
    "record that a reader would need to answer a question about it later.\n\n"
)

COMPACTION_TRIGGER_FRACTION = 0.90
KEPT_PAIRS_LADDER = (10, 5, 2, 0)
CHARS_PER_TOKEN_ESTIMATE = 4  # rough proxy for a hypothetical, not-yet-sent payload

# Measured against real prompt_eval_count: the character estimate underestimates
# in every sample, worst at 3.13 chars per token for code. For a check whose job
# is to be safe, the direction that matters is the one that says a payload fits
# when it does not - so the safety check divides by three, not four.
SAFE_CHARS_PER_TOKEN = 3

# How much of the context the summary may occupy. Half leaves room for the kept
# pairs and the new message; a summary that fills the window has nowhere left to
# put the conversation it is supposed to be serving.
SUMMARY_FRACTION = 0.5

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


def summary_limit(effective_context: int | None) -> int | None:
    """Characters the summary may reach before the oldest facts are let go.

    A fraction of the context rather than a constant, so it scales with the
    model instead of being right for one window and wrong for every other.
    """
    if effective_context is None:
        return None
    return int(effective_context * SUMMARY_FRACTION * SAFE_CHARS_PER_TOKEN)


KEEP_EARLIEST = 5


def bounded(summary: str, limit: int) -> tuple[str, list[str]]:
    """The summary cut to its bound, and the facts dropped to get there.

    Compacting the summary again was tried and measured: it does not shrink,
    because a summary is already a minimal list of distinct facts and the
    instruction says omit nothing - and repeating the pass loses facts anyway.
    Facts accumulate without bound and a bounded space cannot hold them, so
    something has to go. The only question left is whether the user finds out,
    and #32 asks that a long session never *silently* loses information.

    **The middle goes, not the oldest.** Dropping oldest-first is simpler and
    was tried first; it forgot "my cat is called Biscuit" from turn one, which
    is exactly the case COMPACTION_INSTRUCTION already warns about - a brief
    early statement matters as much as a later, longer topic. Early facts tend
    to be the identity-shaped ones, said once and relevant throughout; recent
    facts are the live context. What can be spared is between them.
    """
    lines = summary.splitlines()
    if not lines:
        return summary, []

    header, facts = lines[0], lines[1:]
    dropped: list[str] = []
    while facts and len("\n".join([header, *facts])) > limit:
        # Past the earliest few, take from the front of the rest - the oldest
        # of the middle. When too few remain to have a middle, take the oldest
        # that is left, which only happens at a limit too small to be useful.
        position = KEEP_EARLIEST if len(facts) > KEEP_EARLIEST else 0
        dropped.append(facts.pop(position))
    return "\n".join([header, *facts]), dropped


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
        # The header is its own line so that dropping the oldest fact does not
        # take the header with it and leave the model an unlabelled list.
        content = f"Summary of earlier conversation:\n{compact(backend, model, older)}"

    return [{"role": "system", "content": content}, *kept]


def maybe_compact(
    backend: ModelBackend,
    model: str,
    messages: list[dict[str, str]],
    running_usage: int | None,
    effective_context: int | None,
) -> tuple[list[dict[str, str]], int | None, list[str]]:
    """(possibly-compacted messages, the kept_pairs level used, facts let go).

    Triggers on the REAL running usage from the last completed turn. Escalation
    levels are chosen with the character-based estimate - there is no real
    count for a payload not yet sent.
    """
    if running_usage is None or effective_context is None:
        return messages, None, []
    if running_usage < effective_context * COMPACTION_TRIGGER_FRACTION:
        return messages, None, []

    limit = summary_limit(effective_context)
    for kept_pairs in KEPT_PAIRS_LADDER:
        candidate = compacted_history(backend, model, messages, kept_pairs)
        if candidate is messages:
            continue  # nothing older than this level - try a smaller kept window
        if (
            kept_pairs == 0
            or estimated_tokens(candidate)
            < effective_context * COMPACTION_TRIGGER_FRACTION
        ):
            # Bounded only once a rung is chosen. Trimming candidates the ladder
            # then discards would be work thrown away, and would report facts as
            # forgotten that were never actually let go.
            if limit is None:
                return candidate, kept_pairs, []
            trimmed, dropped = bounded(candidate[0]["content"], limit)
            if dropped:
                candidate = [
                    {"role": "system", "content": trimmed},
                    *candidate[1:],
                ]
            return candidate, kept_pairs, dropped
    return messages, None, []


def _payload_tokens(messages: list[dict[str, str]], overhead: int) -> int:
    """What the assembled payload costs, conservatively, including `overhead`.

    `overhead` is what rides with every request but is not in `messages` - the
    system prompt, held outside history deliberately so compaction can never
    forget it, and therefore never able to be compacted away either.
    """
    chars = sum(len(message.get("content") or "") for message in messages)
    return (chars + overhead) // SAFE_CHARS_PER_TOKEN


def compact_to_fit(
    backend: ModelBackend,
    model: str,
    messages: list[dict[str, str]],
    effective_context: int | None,
    overhead: int = 0,
) -> tuple[list[dict[str, str]], int | None, list[str]]:
    """Compact because the payload will not fit - whatever usage reported.

    `maybe_compact` triggers on the last *completed* turn's reported usage,
    which is `None` on a first turn and can sit just under the threshold while
    the payload is genuinely over. #42 cycle 1 measured a turn refused at 287
    tokens over while a compaction from 1939 tokens to 226 - against a 2000
    context - went unattempted, because the previous turn's usage happened to
    be 50 tokens under the trigger. An eightfold reduction was available and
    unused.

    Same ladder, same `compacted_history`, same bounding: only the reason for
    running is different. Returns unchanged when nothing helps, so the caller
    can tell "compaction fixed it" from "nothing will".
    """
    if effective_context is None:
        return messages, None, []

    limit = summary_limit(effective_context)
    everything: list[dict[str, str]] | None = None  # the kept_pairs=0 rung
    already_dropped: list[str] = []
    for kept_pairs in KEPT_PAIRS_LADDER:
        candidate = compacted_history(backend, model, messages, kept_pairs)
        if candidate is messages:
            continue  # nothing older at this level - try a smaller kept window
        dropped: list[str] = []
        if limit is not None:
            trimmed, dropped = bounded(candidate[0]["content"], limit)
            if dropped:
                candidate = [{"role": "system", "content": trimmed}, *candidate[1:]]
        if kept_pairs == 0:
            everything, already_dropped = candidate, dropped
        if _payload_tokens(candidate, overhead) <= effective_context:
            return candidate, kept_pairs, dropped

    # Nothing on the ladder fits, so what will not fit is the summary itself.
    # Letting it go is the only move left that keeps the session usable, and
    # #42 AC 4 forbids a state where every message, however short, is refused.
    # Measured before this existed: four turns worked, then four consecutive
    # refusals of 80-character messages, each preceded by a re-compaction that
    # achieved nothing.
    #
    # Reported through the same forgotten-facts path as every other loss. This
    # drops more at once than anything else does, which makes saying so more
    # important rather than less - #32 exists because a long session must never
    # lose information *silently*.
    #
    # Only when the history is genuinely what is in the way. If an empty
    # history still would not fit, the prompt and this message alone are over
    # and throwing the conversation away would buy nothing.
    if everything is not None and _payload_tokens([], overhead) <= effective_context:
        header, *facts = everything[0]["content"].splitlines()
        return [], 0, [*already_dropped, *facts]
    return messages, None, []


# What is actually too large, once compaction has already had its turn.
CANNOT_CONTINUE = "cannot-continue"
MESSAGE_TOO_LARGE = "message"
CONVERSATION_TOO_LARGE = "conversation"


def what_will_not_fit(line: str, effective_context: int, overhead: int) -> str:
    """Which of three things is over, so the user can be told only what helps.

    #42 AC 5 asks the message to name what is actually too large and suggest
    only something that would help. Cycle 1 watched the overage stop falling at
    5 tokens while the message shrank to a single character - advice to type
    less, in a case where typing less could never work.

    - `CANNOT_CONTINUE`: the fixed part alone exceeds the context. Nothing the
      user types will ever fit, and AC 6 says to say so rather than let them
      find out by retrying.
    - `MESSAGE_TOO_LARGE`: the fixed part plus this message is over. A shorter
      message genuinely helps.
    - `CONVERSATION_TOO_LARGE`: neither of those, so what tips it is the
      history that compaction has already squeezed as far as it goes. A new
      session is the way out; a shorter message is not.
    """
    if overhead // SAFE_CHARS_PER_TOKEN >= effective_context:
        return CANNOT_CONTINUE
    if (overhead + len(line)) // SAFE_CHARS_PER_TOKEN > effective_context:
        return MESSAGE_TOO_LARGE
    return CONVERSATION_TOO_LARGE

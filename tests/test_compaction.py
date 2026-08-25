"""Compaction mechanics: mechanical correctness with a fake client.

Whether a real summary actually preserves a fact is not something a fake
client can prove - that needs a real model, and is demonstrated live in
cycle 1's log instead (a real fact recalled from a real summary, real text
shrinkage). These tests cover what a fake client can honestly cover: the
right messages get sent, and the reply comes back through untouched.
"""

import axiom
from conftest import StubBackend, feed, history


class RecordingBackend:
    """Stands in for a ModelBackend.

    Returns a fixed summary and records exactly what it was asked to summarize.
    Handed straight to compaction - no module global is patched to install it,
    which is the point of the seam.
    """

    def __init__(self, summary: str) -> None:
        self.summary = summary
        self.calls: list[dict] = []

    def complete(self, model, messages):  # noqa: ANN001
        self.calls.append({"model": model, "messages": messages})
        return self.summary


def test_compact_sends_every_pair_and_returns_the_reply_untouched():
    client = RecordingBackend(summary="A concise summary.")
    pairs = [
        {"role": "user", "content": "My favourite colour is teal."},
        {"role": "assistant", "content": "Teal is a great choice!"},
        {"role": "user", "content": "I have a cat named Biscuit."},
        {"role": "assistant", "content": "Biscuit is a lovely name!"},
    ]

    result = axiom.compaction.compact(client, "qwen2.5:7b", pairs)

    assert result == "A concise summary."
    assert len(client.calls) == 1
    sent = client.calls[0]["messages"]
    assert len(sent) == 1, (
        "the pairs go in as one summarization request, not replayed as history"
    )
    for m in pairs:
        assert m["content"] in sent[0]["content"], (
            f"{m['content']!r} missing from the prompt"
        )


def test_compact_returns_empty_string_not_none_on_a_blank_reply():
    client = RecordingBackend(summary=None)
    result = axiom.compaction.compact(
        client, "qwen2.5:7b", [{"role": "user", "content": "hi"}]
    )
    assert result == ""


def make_pairs(n: int) -> list[dict[str, str]]:
    pairs = []
    for i in range(n):
        pairs.append({"role": "user", "content": f"user turn {i}"})
        pairs.append({"role": "assistant", "content": f"assistant turn {i}"})
    return pairs


def test_compacted_history_replaces_everything_older_than_the_kept_window():
    client = RecordingBackend(summary="summary of the old stuff")
    messages = make_pairs(13)  # 26 entries

    result = axiom.compaction.compacted_history(
        client, "qwen2.5:7b", messages, kept_pairs=5
    )

    assert result[0] == {
        "role": "system",
        # The header is on its own line so that dropping the oldest fact for
        # size does not take the header with it and leave an unlabelled list.
        # Same claim as before - the summary is marked as one - different
        # separator.
        "content": "Summary of earlier conversation:\nsummary of the old stuff",
    }
    assert result[1:] == messages[-10:], "the last 5 pairs (10 entries) must stay raw"
    assert len(result) == 11


def test_compacted_history_kept_pairs_zero_compacts_everything():
    client = RecordingBackend(summary="everything, summarized")
    messages = make_pairs(13)

    result = axiom.compaction.compacted_history(
        client, "qwen2.5:7b", messages, kept_pairs=0
    )

    assert len(result) == 1
    assert result[0]["role"] == "system"
    sent = client.calls[0]["messages"][0]["content"]
    for m in messages:
        assert m["content"] in sent, "every pair must reach compact(), none held back"


def test_compacted_history_returns_unchanged_when_nothing_is_older(monkeypatch=None):
    client = RecordingBackend(summary="should not be called")
    messages = make_pairs(4)  # fewer than the 10-pair kept window

    result = axiom.compaction.compacted_history(
        client, "qwen2.5:7b", messages, kept_pairs=10
    )

    assert result is messages, "AC 11: nothing older than the kept window -> no-op"
    assert client.calls == [], (
        "compact() must not be called when there is nothing to compact"
    )


def test_maybe_compact_leaves_history_untouched_below_the_trigger():
    client = RecordingBackend(summary="should not be called")
    messages = make_pairs(13)

    result, kept_pairs, _ = axiom.compaction.maybe_compact(
        client, "qwen2.5:7b", messages, running_usage=10, effective_context=1000
    )

    assert result is messages
    assert kept_pairs is None
    assert client.calls == []


def test_maybe_compact_leaves_history_untouched_when_context_is_unknown():
    """AC 1's trigger needs an effective_context to compare against - #28's
    own fallback (Ollama's default, axiom doesn't know the number) means
    there is nothing to trigger against, so compaction simply never fires.
    """
    client = RecordingBackend(summary="should not be called")
    messages = make_pairs(13)

    result, kept_pairs, _ = axiom.compaction.maybe_compact(
        client, "qwen2.5:7b", messages, running_usage=999_999, effective_context=None
    )

    assert result is messages
    assert kept_pairs is None
    assert client.calls == []


def test_maybe_compact_escalates_past_a_level_that_still_does_not_fit():
    """A summary that comes back too long to fit even at the first rung
    must escalate to the next one, not stop early.
    """
    huge_summary = "x" * 10_000  # guarantees the 10-pair candidate won't fit
    client = RecordingBackend(summary=huge_summary)
    messages = make_pairs(13)

    result, kept_pairs, _ = axiom.compaction.maybe_compact(
        client, "qwen2.5:7b", messages, running_usage=100, effective_context=100
    )

    assert kept_pairs == 0, (
        "every non-zero rung's candidate is oversized - must reach the floor"
    )
    assert len(client.calls) == len(axiom.compaction.KEPT_PAIRS_LADDER), (
        "one compact() call per rung tried before landing on the floor"
    )


def test_maybe_compact_still_compacts_older_pairs_even_when_kept_pairs_dominate():
    """AC 6: compaction of everything older than the kept window happens
    even when the kept pairs alone account for most of the space.

    Sizes are exact, not guessed: 20 kept entries x 100 chars = 2000 chars
    (500 estimated tokens) - the dominant term by construction - plus a
    near-empty summary of the one old pair, comfortably under a 540-token
    threshold (90% of 600). So kept_pairs=10 fits on the FIRST rung tried;
    the ladder never needs to escalate for this assertion to hold.
    """
    client = RecordingBackend(summary="y")  # ~0 estimated tokens
    old_pair = [
        {"role": "user", "content": "x"},
        {"role": "assistant", "content": "x"},
    ]
    kept_pairs_raw = make_pairs(10)
    for m in kept_pairs_raw:
        m["content"] = m["content"].ljust(100, "z")  # exactly 100 chars each
    messages = old_pair + kept_pairs_raw

    result, kept_pairs, _ = axiom.compaction.maybe_compact(
        client, "qwen2.5:7b", messages, running_usage=600, effective_context=600
    )

    assert kept_pairs == 10, "the dominant kept pairs fit on the first rung tried"
    assert result[0]["role"] == "system", (
        "the one small older pair still got compacted, despite being a tiny "
        "fraction of the total size"
    )
    assert len(client.calls) == 1, "only one compact() call - fit on the first rung"


def test_main_prints_visibility_line_when_compaction_triggers(monkeypatch, capsys):
    """AC 9: the user is told when compaction happens.

    context_length=1000, threshold=900. The first turn's fake response
    reports usage=950 - over threshold - so the SECOND input (checked
    before sending) is the one that should trigger compaction.
    """
    backend = StubBackend(
        info={"qwen2.context_length": 1000}, usage=950, summary="a short summary"
    )
    feed(monkeypatch, ["first message", "second message", "/exit"])

    axiom.main([], using=backend)

    out = capsys.readouterr().out
    assert "compacting" in out.lower(), (
        "no visibility line printed when compaction fired"
    )


def test_main_does_not_print_a_visibility_line_below_threshold(monkeypatch, capsys):
    backend = StubBackend(
        info={"qwen2.context_length": 1000},
        usage=5,  # far under 180
        summary="should not be called",
    )
    feed(monkeypatch, ["first message", "second message", "/exit"])

    axiom.main([], using=backend)

    out = capsys.readouterr().out
    assert "compacting" not in out.lower()
    assert backend.completed == [], "compact() must not run"


def test_compacted_history_persists_and_does_not_re_expand(monkeypatch, capsys):
    """AC 10: once compacted, it stays compacted for the rest of the session -
    the THIRD turn's request must carry the compacted system summary, not
    the original raw pairs, proving state was actually replaced in main(),
    not recomputed fresh (and back to the original) each turn.
    """
    backend = StubBackend(
        info={"qwen2.context_length": 1000},
        usage=950,
        summary="THE-COMPACTED-SUMMARY-MARKER",
    )
    feed(monkeypatch, ["first message", "second message", "third message", "/exit"])

    axiom.main([], using=backend)

    third_turn_messages = history(backend.streamed[2])
    assert third_turn_messages[0]["role"] == "system"
    assert "THE-COMPACTED-SUMMARY-MARKER" in third_turn_messages[0]["content"]
    assert not any(m["content"] == "first message" for m in third_turn_messages), (
        "the original raw pair should be gone, not re-sent alongside the summary"
    )


def test_compacted_history_never_resummarizes_an_existing_summary():
    """The bug found live: a second compaction pass folded an already-
    compacted system-role summary into compact()'s input alongside new
    turns, and the model's fresh summary dropped facts the first pass had
    preserved. Fix: an existing summary is carried forward verbatim; only
    the genuinely new messages after it are ever handed to compact().
    """
    client = RecordingBackend(summary="NEW-FACTS-ONLY")
    prior_summary = {
        "role": "system",
        "content": "Summary of earlier conversation: PRIOR-FACT-MUST-SURVIVE",
    }
    new_turns = make_pairs(3)
    messages = [prior_summary, *new_turns]

    result = axiom.compaction.compacted_history(
        client, "qwen2.5:7b", messages, kept_pairs=0
    )

    assert len(client.calls) == 1, (
        "compact() must be called exactly once - for the new turns only"
    )
    sent = client.calls[0]["messages"][0]["content"]
    assert "PRIOR-FACT-MUST-SURVIVE" not in sent, (
        "the existing summary must never be re-sent to compact() for re-summarization"
    )
    for m in new_turns:
        assert m["content"] in sent, (
            f"{m['content']!r} missing from the new-facts prompt"
        )

    assert len(result) == 1
    assert "PRIOR-FACT-MUST-SURVIVE" in result[0]["content"], (
        "the prior summary must survive verbatim in the result"
    )
    assert "NEW-FACTS-ONLY" in result[0]["content"], "the new summary must be appended"


def test_compacted_history_carries_summary_forward_with_no_new_turns():
    """If everything older than the kept window IS just the prior summary
    (nothing genuinely new since then), compact() should not be called at
    all - there is nothing new to summarize.
    """
    client = RecordingBackend(summary="should not be called")
    prior_summary = {
        "role": "system",
        "content": "Summary of earlier conversation: ONLY-FACT",
    }
    messages = [prior_summary, *make_pairs(1)]  # 1 pair, under any non-zero kept level

    result = axiom.compaction.compacted_history(
        client, "qwen2.5:7b", messages, kept_pairs=10
    )

    assert result is messages, (
        "1 pair is under the 10-pair kept window - nothing older to touch"
    )
    assert client.calls == []


def tool_turn(n: int) -> list[dict]:
    return [
        {"role": "user", "content": f"question {n}"},
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {"function": {"name": "read_file", "arguments": {"path": f"/f{n}"}}}
            ],
        },
        {"role": "tool", "content": f"contents of file {n}", "tool_name": "read_file"},
        {"role": "assistant", "content": f"answer {n}"},
    ]


def plain_turn(n: int) -> list[dict]:
    return [
        {"role": "user", "content": f"question {n}"},
        {"role": "assistant", "content": f"answer {n}"},
    ]


def test_compaction_never_keeps_a_tool_result_without_its_call():
    """AC 20: a turn is not always two messages.

    Cutting inside a tool exchange leaves a tool-role message whose call was
    summarized away - a result for a request the model never made.
    """
    history = []
    for n in range(6):
        history += tool_turn(n) if n % 2 == 0 else plain_turn(n)

    result = axiom.compaction.compacted_history(
        RecordingBackend(summary="S"), "m", list(history), kept_pairs=5
    )

    kept = result[1:]  # everything after the summary
    assert kept[0]["role"] == "user", "the kept window starts mid-turn"
    for position, message in enumerate(kept):
        if message["role"] == "tool":
            assert any("tool_calls" in earlier for earlier in kept[:position]), (
                "a tool result survived without the call that produced it"
            )


def test_what_was_asked_of_a_tool_reaches_the_summary():
    """AC 20: without this, a summary records that a file said something but
    not which file - the fact survives and its subject does not."""
    backend = RecordingBackend(summary="S")

    axiom.compaction.compacted_history(backend, "m", tool_turn(7) * 3, kept_pairs=0)

    summarized = backend.calls[0]["messages"][0]["content"]
    assert "read_file" in summarized
    assert "/f7" in summarized


def test_a_compacted_session_can_still_refer_to_earlier_tool_work():
    """AC 20's second half, end to end: the summary is what carries a tool
    result forward once the raw messages are gone."""
    backend = RecordingBackend(summary="the file /f0 contained: contents of file 0")
    history = tool_turn(0) + [m for n in range(1, 8) for m in plain_turn(n)]

    result = axiom.compaction.compacted_history(backend, "m", history, kept_pairs=2)

    assert result[0]["role"] == "system"
    assert "/f0" in result[0]["content"], (
        "the compacted session cannot answer about work done before compaction"
    )
    assert not any(m["role"] == "tool" for m in result[1:]), (
        "the raw tool message should have been summarized, not kept"
    )


def test_plain_conversations_are_sliced_exactly_as_before():
    """The turn-boundary rule must not change a history with no tool use -
    every boundary in one is already a turn boundary."""
    history = [m for n in range(13) for m in plain_turn(n)]

    result = axiom.compaction.compacted_history(
        RecordingBackend(summary="S"), "m", list(history), kept_pairs=5
    )

    assert result[1:] == history[-10:]


# --- #32: the summary itself outgrowing the window --------------------------


def test_a_payload_that_fits_is_not_reported_as_too_large():
    messages = [{"role": "user", "content": "a" * 300}]

    assert axiom.compaction.too_large(messages, 1000) is None


def test_a_payload_over_the_context_says_how_far_over():
    """AC 3. The divisor is three, not four: measured against real token counts
    the character estimate underestimates by up to 21%, and a check whose job is
    to be safe must not be the one that says a payload fits when it does not.
    """
    messages = [{"role": "user", "content": "a" * 6000}]  # 2000 tokens at 3/char

    over = axiom.compaction.too_large(messages, 1500)

    assert over == 500


def test_the_payload_check_is_silent_without_a_known_context():
    """#28's fallback: with no context established there is nothing to check."""
    assert (
        axiom.compaction.too_large([{"role": "user", "content": "a" * 99999}], None)
        is None
    )


def test_a_normal_turn_is_not_read_as_truncated():
    """Measured: 630 reported against a 906 estimate on a turn that fit."""
    assert axiom.compaction.looks_truncated(906, 630) is False


def test_a_truncated_prompt_is_recognised():
    """Measured: ~4,100 estimated sent, 258 reported, no error raised."""
    assert axiom.compaction.looks_truncated(4134, 258) is True


def test_a_small_payload_is_never_read_as_truncated():
    """The ratio alone is noise here - a four-token shortfall is rounding.

    Caught by the transcript: a stub reporting one token against a five-token
    estimate produced a truncation warning on an ordinary reply.
    """
    assert axiom.compaction.looks_truncated(5, 1) is False
    assert axiom.compaction.looks_truncated(120, 30) is False


def test_no_report_without_a_count():
    assert axiom.compaction.looks_truncated(5000, None) is False
    assert axiom.compaction.looks_truncated(5000, 0) is False


# --- #32: the summary reaching its bound ------------------------------------


def a_summary(lines: int) -> str:
    facts = "\n".join(f"- fact {n} about something" for n in range(lines))
    return f"Summary of earlier conversation:\n{facts}"


def test_a_summary_under_its_bound_keeps_everything():
    trimmed, dropped = axiom.compaction.bounded(a_summary(3), limit=10_000)

    assert dropped == []
    assert trimmed == a_summary(3)


def test_the_middle_goes_not_the_earliest():
    """AC 1, and the reason it is the middle.

    Dropping oldest-first was tried and measured: it forgot "my cat is called
    Biscuit" from turn one. That is the exact case COMPACTION_INSTRUCTION
    already warns about - a brief early statement matters as much as a later,
    longer topic - so the earliest facts stay and the middle goes.
    """
    trimmed, dropped = axiom.compaction.bounded(a_summary(20), limit=250)

    assert dropped, "nothing was let go despite being over the bound"
    assert "- fact 0 about something" in trimmed, "an early fact was forgotten"
    assert "- fact 19 about something" in trimmed, "the newest fact was forgotten"
    assert any("fact 5" in fact or "fact 6" in fact for fact in dropped)
    assert trimmed.startswith("Summary of earlier conversation")
    assert len(trimmed) <= 250


def test_what_was_dropped_is_returned_not_just_counted():
    """AC 2 as amended: a fact may go, but not without the user being able to
    see which. A count would say something went without saying whether it
    mattered."""
    _, dropped = axiom.compaction.bounded(a_summary(20), limit=250)

    assert all(isinstance(fact, str) and fact for fact in dropped)
    assert all("fact" in fact for fact in dropped), "a fact was dropped unnamed"


def test_a_summary_is_never_emptied_completely():
    """Even an impossible bound leaves something. A history of nothing at all
    would be worse than one that is slightly too big, and the payload check is
    what catches the remainder."""
    trimmed, dropped = axiom.compaction.bounded(a_summary(10), limit=1)

    assert trimmed, "the summary was emptied"
    assert trimmed.startswith("Summary of earlier conversation")


def test_the_bound_scales_with_the_context():
    assert axiom.compaction.summary_limit(1000) > axiom.compaction.summary_limit(500)
    assert axiom.compaction.summary_limit(None) is None


def test_maybe_compact_reports_what_it_forgot():
    """The path end to end: over the bound, trimmed, and the facts handed back
    so the session can say what went."""
    backend = RecordingBackend(
        summary="\n".join(
            f"- old fact {n}: something the user mentioned some turns ago"
            for n in range(60)
        )
    )

    result, kept, forgotten = axiom.compaction.maybe_compact(
        backend, "m", make_pairs(13), running_usage=950, effective_context=1000
    )

    assert kept is not None
    assert forgotten, "a summary far past its bound reported nothing forgotten"
    assert len(result[0]["content"]) <= axiom.compaction.summary_limit(1000)


def test_nothing_is_reported_forgotten_when_the_summary_fits():
    backend = RecordingBackend(summary="- one small fact")

    result, kept, forgotten = axiom.compaction.maybe_compact(
        backend, "m", make_pairs(13), running_usage=950, effective_context=1000
    )

    assert kept is not None
    assert forgotten == []

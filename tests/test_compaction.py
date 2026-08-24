"""Compaction mechanics: mechanical correctness with a fake client.

Whether a real summary actually preserves a fact is not something a fake
client can prove - that needs a real model, and is demonstrated live in
cycle 1's log instead (a real fact recalled from a real summary, real text
shrinkage). These tests cover what a fake client can honestly cover: the
right messages get sent, and the reply comes back through untouched.
"""

import builtins

import axiom


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
        "content": "Summary of earlier conversation: summary of the old stuff",
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

    result, kept_pairs = axiom.compaction.maybe_compact(
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

    result, kept_pairs = axiom.compaction.maybe_compact(
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

    result, kept_pairs = axiom.compaction.maybe_compact(
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

    result, kept_pairs = axiom.compaction.maybe_compact(
        client, "qwen2.5:7b", messages, running_usage=600, effective_context=600
    )

    assert kept_pairs == 10, "the dominant kept pairs fit on the first rung tried"
    assert result[0]["role"] == "system", (
        "the one small older pair still got compacted, despite being a tiny "
        "fraction of the total size"
    )
    assert len(client.calls) == 1, "only one compact() call - fit on the first rung"


class ChatAndCompactClient:
    """Handles both call shapes main() makes: the streaming chat loop
    (stream=True) and compact()'s own plain, non-streamed summarization call.
    """

    def __init__(
        self, model_info: dict, prompt_eval_count: int, compact_summary: str
    ) -> None:
        self.model_info = model_info
        self.prompt_eval_count = prompt_eval_count
        self.compact_summary = compact_summary
        self.chat_calls: list[dict] = []

    def show(self, model):  # noqa: ANN001, ARG002
        return type("Info", (), {"modelinfo": self.model_info})()

    def chat(self, model, messages, stream=False, options=None):  # noqa: ANN001, ARG002
        self.chat_calls.append(
            {"messages": [dict(m) for m in messages], "stream": stream}
        )
        if stream:
            chunk = type(
                "Chunk",
                (),
                {
                    "message": type("Msg", (), {"content": "a reply"})(),
                    "prompt_eval_count": self.prompt_eval_count,
                    "eval_count": 0,
                },
            )()
            return iter([chunk])
        return type(
            "Reply",
            (),
            {"message": type("Msg", (), {"content": self.compact_summary})()},
        )()


def feed(monkeypatch, lines: list[str]) -> None:
    supply = iter(lines)

    def fake_input(prompt: str = "") -> str:
        print(prompt, end="")
        try:
            return next(supply)
        except StopIteration:
            raise EOFError from None

    monkeypatch.setattr(builtins, "input", fake_input)


def test_main_prints_visibility_line_when_compaction_triggers(monkeypatch, capsys):
    """AC 9: the user is told when compaction happens.

    context_length=200, threshold=180. The first turn's fake response
    reports prompt_eval_count=190 - over threshold - so the SECOND input
    (checked before sending) is the one that should trigger compaction.
    """
    client = ChatAndCompactClient(
        model_info={"qwen2.context_length": 200},
        prompt_eval_count=190,
        compact_summary="a short summary",
    )
    monkeypatch.setattr(axiom.backend.ollama, "Client", lambda host: client)
    feed(monkeypatch, ["first message", "second message", "/exit"])

    axiom.main([])

    out = capsys.readouterr().out
    assert "compacting" in out.lower(), (
        "no visibility line printed when compaction fired"
    )


def test_main_does_not_print_a_visibility_line_below_threshold(monkeypatch, capsys):
    client = ChatAndCompactClient(
        model_info={"qwen2.context_length": 200},
        prompt_eval_count=5,  # far under 180
        compact_summary="should not be called",
    )
    monkeypatch.setattr(axiom.backend.ollama, "Client", lambda host: client)
    feed(monkeypatch, ["first message", "second message", "/exit"])

    axiom.main([])

    out = capsys.readouterr().out
    assert "compacting" not in out.lower()
    assert not any(c["stream"] is False for c in client.chat_calls), (
        "compact() must not run"
    )


def test_compacted_history_persists_and_does_not_re_expand(monkeypatch, capsys):
    """AC 10: once compacted, it stays compacted for the rest of the session -
    the THIRD turn's request must carry the compacted system summary, not
    the original raw pairs, proving state was actually replaced in main(),
    not recomputed fresh (and back to the original) each turn.
    """
    client = ChatAndCompactClient(
        model_info={"qwen2.context_length": 200},
        prompt_eval_count=190,
        compact_summary="THE-COMPACTED-SUMMARY-MARKER",
    )
    monkeypatch.setattr(axiom.backend.ollama, "Client", lambda host: client)
    feed(monkeypatch, ["first message", "second message", "third message", "/exit"])

    axiom.main([])

    streaming_calls = [c for c in client.chat_calls if c["stream"] is True]
    third_turn_messages = streaming_calls[2]["messages"]
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

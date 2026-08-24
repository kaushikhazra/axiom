"""Compaction mechanics: mechanical correctness with a fake client.

Whether a real summary actually preserves a fact is not something a fake
client can prove - that needs a real model, and is demonstrated live in
cycle 1's log instead (a real fact recalled from a real summary, real text
shrinkage). These tests cover what a fake client can honestly cover: the
right messages get sent, and the reply comes back through untouched.
"""

import axiom


class RecordingClient:
    """Returns a fixed summary, records exactly what it was asked to summarize."""

    def __init__(self, summary: str) -> None:
        self.summary = summary
        self.calls: list[dict] = []

    def chat(self, model, messages):  # noqa: ANN001
        self.calls.append({"model": model, "messages": messages})
        return type(
            "Reply", (), {"message": type("Msg", (), {"content": self.summary})()}
        )()


def test_compact_sends_every_pair_and_returns_the_reply_untouched():
    client = RecordingClient(summary="A concise summary.")
    pairs = [
        {"role": "user", "content": "My favourite colour is teal."},
        {"role": "assistant", "content": "Teal is a great choice!"},
        {"role": "user", "content": "I have a cat named Biscuit."},
        {"role": "assistant", "content": "Biscuit is a lovely name!"},
    ]

    result = axiom.compact(client, "qwen2.5:7b", pairs)

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
    client = RecordingClient(summary=None)
    result = axiom.compact(client, "qwen2.5:7b", [{"role": "user", "content": "hi"}])
    assert result == ""

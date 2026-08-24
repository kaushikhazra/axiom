"""Ctrl-C behaviour, driven by raising the exception the OS would raise.

These do not prove a real Ctrl-C is delivered — see the cycle-6 log for why
that cannot be demonstrated from this shell. They prove what the program does
once the interrupt arrives.
"""

import builtins

import pytest

import axiom


class FakeClient:
    """Stands in for ollama.Client. Interrupts the first stream, then behaves."""

    def __init__(self, host: str) -> None:
        self.host = host
        self.calls: list[list[dict[str, str]]] = []

    def show(self, model):  # noqa: ANN001, ARG002
        # Empty model_info: these tests are about interrupt behaviour, not
        # context sizing, so this exercises the same "Ollama default" path
        # a real unknown-context model would.
        return type("Info", (), {"modelinfo": {}})()

    def chat(self, model, messages, stream, options=None):  # noqa: ANN001, ARG002
        self.calls.append([dict(m) for m in messages])
        if len(self.calls) == 1:
            return self._interrupted_stream()
        return self._plain_stream("second reply")

    @staticmethod
    def _interrupted_stream():
        yield _chunk("partial ")
        yield _chunk("answer")
        raise KeyboardInterrupt

    @staticmethod
    def _plain_stream(text: str):
        yield _chunk(text)


def _chunk(text: str):
    return type(
        "Chunk",
        (),
        {
            "message": type("Msg", (), {"content": text})(),
            "prompt_eval_count": 1,
            "eval_count": 1,
        },
    )()


@pytest.fixture
def client(monkeypatch):
    made: list[FakeClient] = []

    def factory(host):
        made.append(FakeClient(host))
        return made[-1]

    monkeypatch.setattr(axiom.backend.ollama, "Client", factory)
    return made


def feed(monkeypatch, lines: list[str]) -> None:
    supply = iter(lines)

    def fake_input(prompt: str = "") -> str:
        print(prompt, end="")
        try:
            return next(supply)
        except StopIteration:
            raise EOFError from None

    monkeypatch.setattr(builtins, "input", fake_input)


def test_interrupt_mid_stream_does_not_end_the_session(monkeypatch, capsys, client):
    feed(monkeypatch, ["first question", "second question"])
    axiom.main([])

    out = capsys.readouterr()
    assert "cancelled after 14 characters" in out.err
    assert "second reply" in out.out
    assert len(client[0].calls) == 2, "the session kept going after the interrupt"


def test_cancelled_reply_is_absent_from_history(monkeypatch, capsys, client):
    feed(monkeypatch, ["first question", "second question"])
    axiom.main([])
    capsys.readouterr()

    second_call = client[0].calls[1]
    assert [m["content"] for m in second_call] == ["second question"], (
        "the interrupted turn leaked into history"
    )


def test_interrupt_at_idle_prompt_exits(monkeypatch, capsys, client):
    def interrupting_input(prompt: str = "") -> str:
        print(prompt, end="")
        raise KeyboardInterrupt

    monkeypatch.setattr(builtins, "input", interrupting_input)
    axiom.main([])

    assert client[0].calls == [], "the model was called despite an immediate interrupt"

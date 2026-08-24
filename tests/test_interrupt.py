"""Ctrl-C behaviour, driven by raising the exception the OS would raise.

These do not prove a real Ctrl-C is delivered - see the cycle-6 log for why
that cannot be demonstrated from this shell. They prove what the program does
once the interrupt arrives.

The backend is handed to main() directly. Nothing global is patched.
"""

import builtins

import pytest

import axiom
from conftest import StubBackend, feed


@pytest.fixture
def backend() -> StubBackend:
    """Interrupts the first stream, then behaves.

    Empty model_info: these tests are about interrupt behaviour, not context
    sizing, so this exercises the same "Ollama default" path a real
    unknown-context model would.
    """
    return StubBackend(
        info={},
        turns=[["partial ", "answer", KeyboardInterrupt()], ["second reply"]],
    )


def test_interrupt_mid_stream_does_not_end_the_session(monkeypatch, capsys, backend):
    feed(monkeypatch, ["first question", "second question"])
    axiom.main([], using=backend)

    out = capsys.readouterr()
    assert "cancelled after 14 characters" in out.err
    assert "second reply" in out.out
    assert len(backend.streamed) == 2, "the session kept going after the interrupt"


def test_cancelled_reply_is_absent_from_history(monkeypatch, capsys, backend):
    feed(monkeypatch, ["first question", "second question"])
    axiom.main([], using=backend)
    capsys.readouterr()

    second_call = backend.streamed[1]
    assert [m["content"] for m in second_call] == ["second question"], (
        "the interrupted turn leaked into history"
    )


def test_interrupt_at_idle_prompt_exits(monkeypatch, capsys, backend):
    def interrupting_input(prompt: str = "") -> str:
        print(prompt, end="")
        raise KeyboardInterrupt

    monkeypatch.setattr(builtins, "input", interrupting_input)
    axiom.main([], using=backend)

    assert backend.streamed == [], "the model was called despite an immediate interrupt"

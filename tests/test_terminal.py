"""What the user is shown, at the module that shows it.

report_failure carries four distinct messages and a leading-blank-line rule.
The characterization transcript pins all of that down end to end, but it would
only tell you that *something* changed - these say which rule broke.
"""

import builtins

import pytest

from axiom import terminal
from axiom.backend import BackendError, ConnectionLost

HOST = "http://localhost:11434"


def test_announce_shows_the_computed_context(capsys):
    terminal.announce("qwen2.5:7b", HOST, 32768, overridden=False)
    assert capsys.readouterr().out == (
        f"axiom: qwen2.5:7b at {HOST} (context: 32768 tokens)\n"
    )


def test_announce_marks_a_debug_override(capsys):
    terminal.announce("m", HOST, 500, overridden=True)
    assert "context: 500 tokens, debug override" in capsys.readouterr().out


def test_announce_says_ollama_default_when_the_context_is_unknown(capsys):
    terminal.announce("m", HOST, None, overridden=False)
    out = capsys.readouterr().out
    assert "context: Ollama default" in out
    assert "None" not in out, "must not print a fabricated context number"


def test_read_line_strips_what_the_user_typed(monkeypatch):
    monkeypatch.setattr(builtins, "input", lambda prompt="": "  hello  ")
    assert terminal.read_line() == "hello"


@pytest.mark.parametrize("leaving", [EOFError, KeyboardInterrupt])
def test_read_line_returns_none_when_the_user_leaves(monkeypatch, capsys, leaving):
    def departs(prompt: str = "") -> str:
        raise leaving

    monkeypatch.setattr(builtins, "input", departs)
    assert terminal.read_line() is None
    assert capsys.readouterr().out == "\n", (
        "the cursor is mid-line when they leave - close it"
    )


def test_note_compaction_names_the_level(capsys):
    terminal.note_compaction(5)
    assert "compacting older history (keeping the last 5)" in capsys.readouterr().out


def test_note_compaction_says_everything_at_the_floor(capsys):
    terminal.note_compaction(0)
    assert "compacting older history (everything)" in capsys.readouterr().out


def test_a_cancellation_reports_how_much_arrived(capsys):
    terminal.report_failure(KeyboardInterrupt(), "partial ", HOST)
    assert capsys.readouterr().err == "\ncancelled after 8 characters\n"


def test_a_cancellation_opens_a_line_even_with_nothing_on_screen(capsys):
    """The user pressed the key mid-line, so the blank line is unconditional."""
    terminal.report_failure(KeyboardInterrupt(), "", HOST)
    assert capsys.readouterr().err == "\ncancelled after 0 characters\n"


def test_a_refusal_reports_the_model_wording(capsys):
    terminal.report_failure(BackendError("model not found"), "", HOST)
    assert capsys.readouterr().err == "error: model not found\n"


def test_a_refusal_after_a_partial_reply_opens_a_line_first(capsys):
    terminal.report_failure(BackendError("boom"), "partial ", HOST)
    assert capsys.readouterr().err == "\nerror: boom\n"


def test_an_unreachable_backend_names_the_host(capsys):
    terminal.report_failure(ConnectionLost("connection refused"), "", HOST)
    assert capsys.readouterr().err == (
        f"error: cannot reach Ollama at {HOST} (connection refused)\n"
    )


def test_a_reply_cut_off_says_so_and_says_how_much(capsys):
    """Without this the user reads a fragment as though it were the answer."""
    terminal.report_failure(ConnectionLost("connection reset"), "partial ", HOST)
    assert capsys.readouterr().err == (
        f"\nerror: reply cut off after 8 characters "
        f"- lost connection to {HOST} (connection reset)\n"
    )

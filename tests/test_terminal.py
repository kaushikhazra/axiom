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
    terminal.announce("qwen2.5:7b", HOST, 32768, overridden=False, tools=5, web=True)
    assert capsys.readouterr().out == (
        f"axiom: qwen2.5:7b at {HOST} (context: 32768 tokens, 5 tools including web)\n"
    )


def test_announce_marks_a_debug_override(capsys):
    terminal.announce("m", HOST, 500, overridden=True, tools=5)
    assert "context: 500 tokens, debug override" in capsys.readouterr().out


def test_announce_says_ollama_default_when_the_context_is_unknown(capsys):
    terminal.announce("m", HOST, None, overridden=False, tools=5)
    out = capsys.readouterr().out
    assert "context: Ollama default" in out
    assert "None" not in out, "must not print a fabricated context number"


def test_announce_says_when_tools_are_switched_off(capsys):
    """AC 34: the user has to be able to see their own choice took effect."""
    terminal.announce("m", HOST, 32768, overridden=False, tools=0)
    assert "tools off" in capsys.readouterr().out


def test_announce_says_when_the_model_cannot_call_tools(capsys):
    """AC 2: a fact about the model, said in plain terms - and distinct from
    the user having switched them off, which they can undo."""
    terminal.announce("m", HOST, 32768, overridden=False, tools=None)
    out = capsys.readouterr().out
    assert "cannot call them" in out
    assert "tools off" not in out


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


def test_announce_says_the_web_is_available(capsys):
    """AC 1: a tool count alone says nothing about whether the web is reachable."""
    terminal.announce("m", HOST, 32768, overridden=False, tools=7, web=True)
    assert "7 tools including web" in capsys.readouterr().out


def test_announce_says_when_the_web_is_off_but_tools_are_not(capsys):
    """AC 29, and it must not read as though all tools were lost."""
    terminal.announce("m", HOST, 32768, overridden=False, tools=5, web=False)
    out = capsys.readouterr().out
    assert "5 tools, web off" in out
    assert "tools off" not in out


def test_announce_says_nothing_about_the_web_when_there_are_no_tools(capsys):
    """Two three-state settings would be nine sentences. With no tools there is
    nothing true to say about the web, so the line does not say anything."""
    terminal.announce("m", HOST, 32768, overridden=False, tools=0, web=False)
    assert capsys.readouterr().out.count("web") == 0

    terminal.announce("m", HOST, 32768, overridden=False, tools=None, web=True)
    assert capsys.readouterr().out.count("web") == 0

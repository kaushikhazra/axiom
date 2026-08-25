"""Models that announce a tool call as text rather than as a structured call.

qwen2.5-coder:7b does exactly this - bare JSON in the reply, tool_calls absent,
streamed token by token so no single piece is recognisable. The captured shape
is in this loop's cycle-7 log.

Nothing here names a model. The rule is about the shape of a reply.
"""

import axiom
from axiom.backend import call_from_text
from conftest import StubBackend, feed

KNOWN = {"read_file", "run_command"}


def test_a_json_call_is_recognised():
    call = call_from_text('{"name": "read_file", "arguments": {"path": "/x"}}', KNOWN)

    assert call is not None
    assert call.name == "read_file"
    assert call.arguments == {"path": "/x"}


def test_surrounding_whitespace_does_not_hide_a_call():
    assert call_from_text('\n  {"name": "read_file", "arguments": {}}  \n', KNOWN)


def test_prose_is_not_a_call():
    assert call_from_text("The file says Biscuit is ginger.", KNOWN) is None


def test_json_naming_no_tool_we_have_is_not_a_call():
    """Otherwise a model discussing JSON would have its answer eaten."""
    assert call_from_text('{"name": "launch_missiles", "arguments": {}}', KNOWN) is None


def test_json_that_is_not_an_object_is_not_a_call():
    assert call_from_text('["read_file"]', KNOWN) is None


def test_broken_json_is_not_a_call():
    assert call_from_text('{"name": "read_file", "arguments":', KNOWN) is None


def test_a_text_announced_call_runs_and_is_never_printed(monkeypatch, capsys, tmp_path):
    """AC 6: carried out, and not shown to the user as prose."""
    target = tmp_path / "notes.txt"
    target.write_text("Biscuit the cat is ginger.\n", encoding="utf-8")
    announcement = (
        '{"name": "read_file", "arguments": {"path": ' + f'"{target.as_posix()}"' + "}}"
    )
    backend = StubBackend(turns=[[announcement], ["The cat is ginger."]])
    feed(monkeypatch, ["what colour is the cat?", "/exit"])

    axiom.main([], using=backend)
    out = capsys.readouterr().out

    assert "read_file" in out, "the user should still see what ran"
    assert '{"name"' not in out, "the raw call was shown to the user"
    assert "Biscuit the cat is ginger." in out, "the tool did not run"
    assert "The cat is ginger." in out


def test_the_call_reaches_the_model_as_a_proper_tool_exchange(
    monkeypatch, capsys, tmp_path
):
    """However the model announced it, what goes back into history is the same
    shape as for a structured call - or the model cannot match the result."""
    target = tmp_path / "notes.txt"
    target.write_text("ginger", encoding="utf-8")
    announcement = (
        '{"name": "read_file", "arguments": {"path": ' + f'"{target.as_posix()}"' + "}}"
    )
    backend = StubBackend(turns=[[announcement], ["done"]])
    feed(monkeypatch, ["read it", "/exit"])

    axiom.main([], using=backend)
    capsys.readouterr()

    second = backend.streamed[1]
    assert second[-2]["tool_calls"][0]["function"]["name"] == "read_file"
    assert second[-1] == {
        "role": "tool",
        "content": "ginger",
        "tool_name": "read_file",
    }


def test_prose_that_begins_with_a_brace_is_still_printed_in_full(monkeypatch, capsys):
    """The case that silently eats an answer.

    A reply is held back while it might be a call. One that opens with a brace
    and turns out to be prose must arrive complete and in order.
    """
    prose = "{ this is not JSON at all, just an awkward way to start a sentence."
    backend = StubBackend(turns=[[prose]])
    feed(monkeypatch, ["say something odd", "/exit"])

    axiom.main([], using=backend)

    assert prose in capsys.readouterr().out


def test_json_that_names_no_tool_is_printed_not_swallowed(monkeypatch, capsys):
    backend = StubBackend(turns=[['{"name": "not_a_tool", "arguments": {}}']])
    feed(monkeypatch, ["show me some json", "/exit"])

    axiom.main([], using=backend)

    assert '"not_a_tool"' in capsys.readouterr().out


def test_a_call_with_unusable_arguments_is_reported_not_dropped(monkeypatch, capsys):
    """AC 6 allows "reported as one axiom could not make". It does not allow
    silence, and it does not allow printing the raw call as an answer."""
    backend = StubBackend(
        turns=[['{"name": "read_file", "arguments": "not-a-mapping"}'], ["oh dear"]]
    )
    feed(monkeypatch, ["read something", "/exit"])

    axiom.main([], using=backend)
    out = capsys.readouterr().out

    assert "error:" in out
    assert '{"name"' not in out


def test_an_ordinary_reply_still_streams_piece_by_piece(monkeypatch, capsys):
    """Withholding must not become buffering for models that behave.

    Asserted on the sequence of writes, not the final text - a reply delivered
    in one lump at the end would pass a content-only check.
    """
    written = []
    backend = StubBackend(turns=[[*"hello there"]])
    feed(monkeypatch, ["hi", "/exit"])

    real_show = axiom.terminal.show_piece
    monkeypatch.setattr(
        axiom.terminal,
        "show_piece",
        lambda text: (written.append(text), real_show(text))[1],
    )

    axiom.main([], using=backend)
    capsys.readouterr()

    assert "".join(written) == "hello there"
    assert len([w for w in written if w]) > 1, "the reply arrived in one lump"

"""What the chat loop does when a model asks for work.

Driven by a stub backend handed to main(), so no model is involved and nothing
is patched. Tools that touch the filesystem stay inside tmp_path.
"""

import axiom
from axiom.backend import BackendError, Call, ConnectionLost
from conftest import StubBackend, feed, history


def read_call(path) -> Call:
    return Call("read_file", {"path": str(path)})


def seeded(tmp_path, text: str = "Biscuit the cat is ginger.\n"):
    target = tmp_path / "notes.txt"
    target.write_text(text, encoding="utf-8")
    return target


def test_a_tool_result_goes_back_as_a_tool_message(monkeypatch, capsys, tmp_path):
    """AC 18 and AC 19: the result reaches the model, tagged with which tool
    produced it, or the model cannot match it to what it asked for."""
    target = seeded(tmp_path)
    backend = StubBackend(turns=[[read_call(target)], ["it is ginger"]])
    feed(monkeypatch, ["what colour is the cat?", "/exit"])

    axiom.main([], using=backend)
    capsys.readouterr()

    second_request = history(backend.streamed[1])
    assistant, tool_message = second_request[-2], second_request[-1]
    assert assistant["role"] == "assistant"
    assert assistant["tool_calls"][0]["function"]["name"] == "read_file"
    assert tool_message == {
        "role": "tool",
        "content": "Biscuit the cat is ginger.\n",
        "tool_name": "read_file",
    }


def test_the_user_is_not_asked_again_between_steps(monkeypatch, capsys, tmp_path):
    """AC 17: one line typed, two model turns, no second prompt."""
    target = seeded(tmp_path)
    backend = StubBackend(turns=[[read_call(target)], ["it is ginger"]])
    feed(monkeypatch, ["what colour is the cat?", "/exit"])

    axiom.main([], using=backend)

    assert len(backend.streamed) == 2
    assert "it is ginger" in capsys.readouterr().out


def test_several_calls_in_one_turn_all_run(monkeypatch, capsys, tmp_path):
    first = tmp_path / "one.txt"
    first.write_text("first", encoding="utf-8")
    second = tmp_path / "two.txt"
    second.write_text("second", encoding="utf-8")
    backend = StubBackend(turns=[[read_call(first), read_call(second)], ["both read"]])
    feed(monkeypatch, ["read both", "/exit"])

    axiom.main([], using=backend)
    capsys.readouterr()

    results = [m for m in backend.streamed[1] if m.get("role") == "tool"]
    assert [m["content"] for m in results] == ["first", "second"]


def test_a_model_that_never_stops_calling_is_stopped(monkeypatch, capsys, tmp_path):
    """Without a bound, a model that answers every result with another call
    would hold the session forever and never hand back."""
    target = seeded(tmp_path)
    backend = StubBackend(turns=[[read_call(target)] for _ in range(20)])
    feed(monkeypatch, ["go", "/exit"])

    axiom.main([], using=backend)
    capsys.readouterr()

    assert len(backend.streamed) == axiom.MAX_TOOL_ROUNDS


def test_a_failing_tool_leaves_the_turn_running(monkeypatch, capsys, tmp_path):
    """AC 28: axiom is told what failed and can carry on in the same turn."""
    backend = StubBackend(
        turns=[[read_call(tmp_path / "missing.txt")], ["I could not read it"]]
    )
    feed(monkeypatch, ["read the file", "/exit"])

    axiom.main([], using=backend)
    out = capsys.readouterr().out

    told = [m for m in backend.streamed[1] if m.get("role") == "tool"][0]
    assert told["content"].startswith("error:")
    assert "missing.txt" in told["content"]
    assert "I could not read it" in out, "the turn carried on after the failure"


def test_the_user_sees_what_ran_and_can_tell_it_from_the_answer(
    monkeypatch, capsys, tmp_path
):
    """AC 21 and AC 22."""
    target = seeded(tmp_path)
    backend = StubBackend(turns=[[read_call(target)], ["it is ginger"]])
    feed(monkeypatch, ["what colour?", "/exit"])

    axiom.main([], using=backend)
    out = capsys.readouterr().out

    assert f"read_file(path={target})" in out, "no sign of what was about to run"
    assert "  | Biscuit the cat is ginger." in out, "tool output is not marked"
    assert "\nit is ginger" in out or "it is ginger" in out


def test_large_tool_output_is_shortened_and_says_how_much(
    monkeypatch, capsys, tmp_path
):
    """AC 23: a big file must not scroll the conversation away."""
    target = tmp_path / "big.txt"
    target.write_text("x" * 5000, encoding="utf-8")
    backend = StubBackend(turns=[[read_call(target)], ["read it"]])
    feed(monkeypatch, ["read the big file", "/exit"])

    axiom.main([], using=backend)
    out = capsys.readouterr().out

    assert "more characters not shown" in out
    assert str(5000 - axiom.terminal.TOOL_OUTPUT_LIMIT) in out
    assert out.count("x") <= axiom.terminal.TOOL_OUTPUT_LIMIT + 10


def test_the_model_still_receives_the_whole_result(monkeypatch, capsys, tmp_path):
    """Truncation is a screen concern. Shortening what the model is told would
    silently change the answer it gives."""
    target = tmp_path / "big.txt"
    target.write_text("x" * 5000, encoding="utf-8")
    backend = StubBackend(turns=[[read_call(target)], ["read it"]])
    feed(monkeypatch, ["read the big file", "/exit"])

    axiom.main([], using=backend)
    capsys.readouterr()

    told = [m for m in backend.streamed[1] if m.get("role") == "tool"][0]
    assert len(told["content"]) == 5000


def test_a_turn_that_fails_after_a_tool_ran_leaves_no_trace(
    monkeypatch, capsys, tmp_path
):
    """The turn is all-or-nothing. A half-finished turn left in history would
    be replayed to the model on the next request as though it had happened."""
    target = seeded(tmp_path)
    backend = StubBackend(
        turns=[
            [read_call(target)],
            [ConnectionLost("connection reset")],
            ["a fresh answer"],
        ]
    )
    feed(monkeypatch, ["read it", "try again", "/exit"])

    axiom.main([], using=backend)
    capsys.readouterr()

    third_request = history(backend.streamed[2])
    assert [m["content"] for m in third_request] == ["try again"], (
        "the failed turn left history behind"
    )


def test_no_tools_are_sent_to_a_model_that_cannot_use_them(monkeypatch, capsys):
    """AC 2's precondition: sending tools to a model without support is a 400,
    so support is asked about before anything is sent."""
    backend = StubBackend(tools_supported=False, turns=[["hello"]])
    feed(monkeypatch, ["hi", "/exit"])

    axiom.main([], using=backend)
    capsys.readouterr()

    assert backend.tools_sent == [None]


def test_tools_are_sent_to_a_model_that_can(monkeypatch, capsys):
    backend = StubBackend(turns=[["hello"]])
    feed(monkeypatch, ["hi", "/exit"])

    axiom.main([], using=backend)
    capsys.readouterr()

    assert backend.tools_sent[0], "a capable model was told about no tools"
    assert backend.tools_sent[0][0]["function"]["name"] in axiom.tools.REGISTRY


def test_a_tool_failure_reads_differently_from_a_model_failure(
    monkeypatch, capsys, tmp_path
):
    """AC 31: three ways a turn can go wrong, and the user must be able to tell
    which happened - a failed tool is worth retrying differently from a model
    that refused or a connection that dropped.
    """
    feed(monkeypatch, ["read it", "/exit"])
    axiom.main(
        [],
        using=StubBackend(
            turns=[[read_call(tmp_path / "missing.txt")], ["could not read it"]]
        ),
    )
    tool_failure = capsys.readouterr()

    feed(monkeypatch, ["say hi", "/exit"])
    axiom.main([], using=StubBackend(turns=[[BackendError("model refused")]]))
    model_failure = capsys.readouterr()

    feed(monkeypatch, ["say hi", "/exit"])
    axiom.main([], using=StubBackend(turns=[[ConnectionLost("connection reset")]]))
    lost_connection = capsys.readouterr()

    # A failed tool is reported inside the tool's own marked output, on stdout,
    # and the turn carries on afterwards.
    assert "  | error:" in tool_failure.out
    assert tool_failure.err == "", "a tool failure is not a session-level failure"
    assert "could not read it" in tool_failure.out

    # The other two end the turn and are reported on stderr, unmarked.
    assert "error: model refused" in model_failure.err
    assert "  |" not in model_failure.err

    assert "cannot reach Ollama" in lost_connection.err
    assert lost_connection.err != model_failure.err, (
        "a refusal and a dropped connection carry different advice"
    )

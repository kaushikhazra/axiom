"""Changing model mid-conversation, and what survives it.

Every test settles a criterion of #49 against a stub. Nothing reaches a real
Ollama.

The criteria that matter most here are payload facts, not printed ones: AC 10,
AC 11 and AC 12 are about what the *new model is sent*, and AC 15 and AC 16
about what the backend was *asked*. Printed output cannot tell a correct
implementation from one that quietly started a fresh conversation, or from one
still interrogating the old model - #48 AC 29 was exactly that mistake.
"""

import json

import pytest

from axiom import backend, main, models
from axiom.backend import Call
from conftest import StubBackend, feed


HOST = "http://localhost:11434"
INSTALLED = ["gemma2:2b", "qwen2.5-coder:7b", "gemma4:e2b", "ornith:9b", "qwen2.5:7b"]
SORTED = ("gemma2:2b", "gemma4:e2b", "ornith:9b", "qwen2.5-coder:7b", "qwen2.5:7b")


@pytest.fixture
def choice(tmp_path, monkeypatch):
    where = tmp_path / ".axiom" / "model.json"
    monkeypatch.setattr(models, "DEFAULT_CHOICE_FILE", where)
    return where


def run(capsys, monkeypatch, typed, argv=None, **stub):
    """A session started on a known model, then driven by `typed`."""
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    stub.setdefault("models", INSTALLED)
    made = StubBackend(**stub)
    feed(monkeypatch, [*typed, "/exit"])
    main(argv or ["--model", "qwen2.5:7b"], using=made)
    return made, capsys.readouterr()


# --- Asking for the switch ----------------------------------------------


def test_the_command_shows_the_list_and_sends_nothing(capsys, monkeypatch, choice):
    """AC 1."""
    stub, out = run(capsys, monkeypatch, ["/model", "2"])

    assert f"models on {HOST}" in out.out
    # Nothing was sent to the model: the only streams are from real messages,
    # and there were none.
    assert stub.streamed == []


def test_the_list_matches_the_one_shown_at_startup(capsys, monkeypatch, choice):
    """AC 2. Same contents, same order, same numbering.

    Driven from a host order that is not sorted, so a second implementation
    that passed the host's order through would show different numbers here.
    """
    _, switching = run(capsys, monkeypatch, ["/model", "2"])
    numbered = [
        line for line in switching.out.splitlines() if line.strip()[:1].isdigit()
    ]

    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    feed(monkeypatch, ["1", "/exit"])
    main([], using=StubBackend(models=INSTALLED))
    at_startup = [
        line
        for line in capsys.readouterr().out.splitlines()
        if line.strip()[:1].isdigit()
    ]

    strip = lambda rows: [r.split(". ", 1)[1].split("  ")[0] for r in rows]  # noqa: E731
    assert strip(numbered) == strip(at_startup) == list(SORTED)


def test_the_model_in_use_is_marked_as_current(capsys, monkeypatch, choice):
    """AC 3."""
    _, out = run(capsys, monkeypatch, ["/model", "2"])

    assert "qwen2.5:7b  (current)" in out.out


def test_a_number_switches(capsys, monkeypatch, choice):
    """AC 4."""
    stub, out = run(capsys, monkeypatch, ["/model", "3", "hello"])

    assert f"now {SORTED[2]}" in out.out
    assert stub.asked_about[-1] == SORTED[2]


def test_an_empty_line_keeps_the_current_model(capsys, monkeypatch, choice):
    """AC 5. Enter accepts nothing here - there is nothing to accept."""
    stub, out = run(capsys, monkeypatch, ["/model", "", "hello"])

    assert "still qwen2.5:7b" in out.out
    assert "now " not in out.out
    assert stub.asked_about[-1] == "qwen2.5:7b"


def test_a_name_switches_directly_with_no_list(capsys, monkeypatch, choice):
    """AC 6."""
    stub, out = run(capsys, monkeypatch, ["/model ornith:9b", "hello"])

    assert "models on" not in out.out
    assert "which model?" not in out.out
    assert "now ornith:9b" in out.out


def test_a_name_must_match_exactly_tag_included(capsys, monkeypatch, choice):
    """AC 7. Ollama reads a bare name as `:latest` and would land elsewhere."""
    stub, out = run(capsys, monkeypatch, ["/model qwen2.5", "1"])

    assert f"qwen2.5 is not installed on {HOST}" in out.err
    assert "qwen2.5:7b" not in out.err.split("is not installed")[0]


def test_an_unknown_name_is_reported_then_the_list_is_shown(
    capsys, monkeypatch, choice
):
    """AC 8."""
    stub, out = run(capsys, monkeypatch, ["/model absent:70b", "3", "hello"])

    assert "absent:70b is not installed" in out.err
    assert "models on" in out.out
    assert f"now {SORTED[2]}" in out.out


def test_an_unknown_name_does_not_change_the_model_before_a_choice(
    capsys, monkeypatch, choice
):
    """AC 8."""
    stub, out = run(capsys, monkeypatch, ["/model absent:70b", ""])

    assert "still qwen2.5:7b" in out.out
    assert "absent:70b" not in stub.asked_about


def test_a_message_that_merely_contains_the_word_is_a_message(
    capsys, monkeypatch, choice
):
    """AC 9."""
    stub, out = run(capsys, monkeypatch, ["what is the /model command?"])

    assert "models on" not in out.out
    sent = stub.streamed[-1]
    assert any(m.get("content") == "what is the /model command?" for m in sent)


# --- What carries across -------------------------------------------------


def test_the_conversation_carries_into_the_new_model(capsys, monkeypatch, choice):
    """AC 10. Measured on the payload, not on a reply coming back."""
    stub, _ = run(
        capsys, monkeypatch, ["first question", "/model", "3", "second question"]
    )

    after = stub.streamed[-1]
    contents = [m.get("content") for m in after]
    assert "first question" in contents, "the new model was not sent what came before"
    assert "second question" in contents


def test_tool_calls_already_in_history_carry_across_unchanged(
    capsys, monkeypatch, choice
):
    """AC 11, the hardest criterion here.

    A conversation holding an `assistant` message with `tool_calls` and a
    `tool` message, carried into a model that cannot call tools. Kaushik's
    decision: they are not removed, not rewritten, and the session does not
    end. The user simply gets no tools from here on.
    """
    stub = StubBackend(
        models=INSTALLED,
        turns=[[Call("read_file", {"path": "x.txt"})], ["done"], ["still here"]],
        # The destination really cannot call tools. Without this the stub says
        # every model can, and the test would prove nothing about the case its
        # name describes - a scenario whose behaviour does not match its name
        # is read as evidence of something that is not happening.
        capable={"qwen2.5:7b": True, "gemma2:2b": False},
    )
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    feed(monkeypatch, ["read x.txt", "/model gemma2:2b", "and now?", "/exit"])
    main(["--model", "qwen2.5:7b"], using=stub)

    assert stub.tools_sent[-1] is None, "the destination could still call tools"
    after = stub.streamed[-1]
    calls = [m for m in after if m.get("tool_calls")]
    results = [m for m in after if m.get("role") == "tool"]

    assert calls, "the assistant's tool call was dropped on the switch"
    assert calls[0]["tool_calls"][0]["function"]["name"] == "read_file"
    assert results, "the tool result was dropped on the switch"
    assert results[0]["tool_name"] == "read_file"


def test_a_switch_to_a_tool_less_model_does_not_end_the_session(
    capsys, monkeypatch, choice
):
    """AC 11."""
    stub, out = run(capsys, monkeypatch, ["hello", "/model gemma2:2b", "still there?"])

    assert len(stub.streamed) == 2, "the session stopped answering after the switch"


def test_nothing_on_screen_is_rewritten_by_a_switch(capsys, monkeypatch, choice):
    """AC 12. The reply from before the switch is still where it was."""
    stub, out = run(capsys, monkeypatch, ["first", "/model", "3", "second"])

    assert out.out.index("a reply") < out.out.index("now ")


def test_everything_that_is_not_the_model_is_unchanged(capsys, monkeypatch, choice):
    """AC 13. The working directory reaches the model through the prompt."""
    stub, _ = run(
        capsys,
        monkeypatch,
        ["first", "/model", "3", "second"],
        argv=["--model", "qwen2.5:7b", "--working-directory", "C:/Projects/.tmp"],
    )

    before, after = stub.streamed[0][0], stub.streamed[-1][0]
    assert before == after, "the standing instructions changed under the switch"
    assert (
        "C:/Projects/.tmp" in after["content"]
        or "C:\\Projects\\.tmp" in after["content"]
    )


def test_running_servers_are_not_restarted(capsys, monkeypatch, choice, tmp_path):
    """AC 14. Identity, not merely that tools still work."""
    config = tmp_path / "mcp.json"
    config.write_text(
        json.dumps({"mcpServers": {"probe": {"command": "not-a-program"}}}),
        encoding="utf-8",
    )
    stub, out = run(
        capsys,
        monkeypatch,
        ["/model", "3", "hello"],
        argv=["--model", "qwen2.5:7b", "--mcp-file", str(config)],
    )

    # Announced once, at startup - not again on the switch.
    assert out.out.count("starting 1 MCP server") == 1


# --- What changes --------------------------------------------------------


def test_the_context_becomes_the_new_models(capsys, monkeypatch, choice):
    """AC 15. Two models, two windows - so the number can only be the new one.

    A single `info` for every model would print an identical line whether the
    switch adopted the new window or kept the old, which is the shape that let
    #48 AC 29 pass with no real test at all.
    """
    stub, out = run(
        capsys,
        monkeypatch,
        ["/model", "3", "hello"],
        infos={
            "qwen2.5:7b": {"qwen2.context_length": 32768},
            "ornith:9b": {"qwen35.context_length": 4096},
        },
    )

    assert "32768 tokens" in out.out, "the startup window was never the old model's"
    assert "now ornith:9b (context: 4096 tokens" in out.out
    assert stub.options[-1] == {"num_ctx": 4096}, "sent the old model's window"


def test_tool_availability_becomes_the_new_models(capsys, monkeypatch, choice):
    """AC 16. Asserted on what the backend was asked, not on the printed line."""
    stub, out = run(capsys, monkeypatch, ["/model", "3", "hello"])

    assert stub.asked_about[-1] == SORTED[2]
    assert "qwen2.5:7b" not in stub.asked_about[-2:]


def test_switching_to_a_tool_less_model_drops_the_tools_and_says_so(
    capsys, monkeypatch, choice
):
    """AC 16, the direction that matters most.

    `gemma2:2b` is the real instrument for this - it is the one model on this
    machine with no tool support - and the criterion is that the session ends
    up with none, said out loud.
    """
    stub, out = run(
        capsys,
        monkeypatch,
        ["/model gemma2:2b", "hello"],
        capable={"qwen2.5:7b": True, "gemma2:2b": False},
    )

    assert "7 tools including web" in out.out, "the session did not start with tools"
    assert "no tools - this model cannot call them" in out.out
    assert stub.tools_sent[-1] is None, "sent tools to a model that cannot use them"


def test_switching_back_to_a_capable_model_restores_the_tools(
    capsys, monkeypatch, choice
):
    """AC 16, the other direction."""
    stub, out = run(
        capsys,
        monkeypatch,
        ["/model gemma2:2b", "/model ornith:9b", "hello"],
        capable={"qwen2.5:7b": True, "gemma2:2b": False, "ornith:9b": True},
    )

    assert "now ornith:9b" in out.out
    assert "7 tools" in out.out.split("now ornith:9b")[1]
    assert stub.tools_sent[-1] is not None, "the tools were not restored"


def test_switching_sends_no_message_by_itself(capsys, monkeypatch, choice):
    """AC 17."""
    stub, _ = run(capsys, monkeypatch, ["/model", "3"])

    assert stub.streamed == []


# --- Remembering ---------------------------------------------------------


def test_a_switch_by_number_is_remembered(capsys, monkeypatch, choice):
    """AC 20."""
    run(capsys, monkeypatch, ["/model", "3"])

    assert json.loads(choice.read_text(encoding="utf-8")) == {HOST: SORTED[2]}


def test_a_switch_by_name_is_remembered(capsys, monkeypatch, choice):
    """AC 20. A name typed at the prompt is the user picking, unlike a flag."""
    run(capsys, monkeypatch, ["/model ornith:9b"])

    assert json.loads(choice.read_text(encoding="utf-8")) == {HOST: "ornith:9b"}


def test_leaving_the_list_without_switching_remembers_nothing(
    capsys, monkeypatch, choice
):
    """AC 21."""
    run(capsys, monkeypatch, ["/model", ""])

    assert not choice.exists()


def test_a_refused_name_remembers_nothing(capsys, monkeypatch, choice):
    """AC 22."""
    run(capsys, monkeypatch, ["/model absent:70b", ""])

    assert not choice.exists()


# --- Getting it wrong ----------------------------------------------------


def test_a_number_outside_the_list_is_refused(capsys, monkeypatch, choice):
    """AC 24."""
    stub, out = run(capsys, monkeypatch, ["/model", "9", "3"])

    assert "there is no model 9" in out.err
    assert f"now {SORTED[2]}" in out.out


def test_something_that_is_neither_a_number_nor_a_name_is_refused(
    capsys, monkeypatch, choice
):
    """AC 25."""
    stub, out = run(capsys, monkeypatch, ["/model", "nonsense", "3"])

    assert "is not a number" in out.err


def test_ctrl_c_at_the_list_cancels_and_keeps_the_session(capsys, monkeypatch, choice):
    """AC 26. Cancels the switch - it does not end the session."""
    stub, out = run(capsys, monkeypatch, ["/model", KeyboardInterrupt(), "still here?"])

    assert "still qwen2.5:7b" in out.out
    assert len(stub.streamed) == 1, "the session ended instead of carrying on"


# --- Boundaries ----------------------------------------------------------


def test_one_installed_model_says_there_is_nothing_to_switch_to(
    capsys, monkeypatch, choice
):
    """AC 27."""
    stub, out = run(
        capsys,
        monkeypatch,
        ["/model", "hello"],
        models=["solo:1b"],
        argv=["--model", "solo:1b"],
    )

    assert "nothing to switch to" in out.out
    assert "which model?" not in out.out


def test_switching_to_the_model_already_in_use_changes_nothing(
    capsys, monkeypatch, choice
):
    """AC 28. Accepted, not an error, and the conversation is untouched."""
    stub, out = run(capsys, monkeypatch, ["first", "/model qwen2.5:7b", "second"])

    assert "still qwen2.5:7b" in out.out
    assert "error" not in out.err
    contents = [m.get("content") for m in stub.streamed[-1]]
    assert "first" in contents


def test_the_command_works_before_anything_has_been_said(capsys, monkeypatch, choice):
    """AC 29."""
    stub, out = run(capsys, monkeypatch, ["/model", "3", "hello"])

    assert f"now {SORTED[2]}" in out.out
    assert len(stub.streamed) == 1


# --- Failure -------------------------------------------------------------


class Flaky(StubBackend):
    """A host that answers at startup and refuses once the session is running."""

    def installed(self):
        if self.streamed or self.asked_about.count("qwen2.5:7b") > 1:
            raise backend.ConnectionLost("refused")
        return list(self.models)


def test_an_unreachable_host_at_switch_time_does_not_end_the_session(
    capsys, monkeypatch, choice
):
    """AC 30, AC 32. The opposite of #48 AC 31, which exits."""
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    stub = Flaky(models=INSTALLED)
    feed(monkeypatch, ["hello", "/model", "still there?", "/exit"])

    main(["--model", "qwen2.5:7b"], using=stub)
    out = capsys.readouterr()

    assert "cannot reach Ollama" in out.err
    assert "staying on qwen2.5:7b" in out.err
    assert len(stub.streamed) == 2, "the session ended on a failed switch"


# --- Exit ----------------------------------------------------------------


def test_ctrl_d_at_the_list_ends_the_session(capsys, monkeypatch, choice):
    """AC 33. Deliberately unlike Ctrl-C: input has genuinely ended."""
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    stub = StubBackend(models=INSTALLED)
    feed(monkeypatch, ["/model", EOFError(), "never read"])

    main(["--model", "qwen2.5:7b"], using=stub)

    assert stub.streamed == [], "carried on after input ended"


@pytest.mark.parametrize("leaving", ["/exit", "/quit"])
def test_exit_behaves_as_before_after_a_switch(capsys, monkeypatch, choice, leaving):
    """AC 34."""
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    stub = StubBackend(models=INSTALLED)
    feed(monkeypatch, ["/model", "3", "hello", leaving, "never read"])

    main(["--model", "qwen2.5:7b"], using=stub)

    assert len(stub.streamed) == 1

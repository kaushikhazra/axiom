"""Which model a run uses: the list, the question, and what is remembered.

Every test here settles a criterion of #48 against a stub. Nothing reaches a
real Ollama - the suite has to stay green with no host running, and this is the
one issue where that is easy to lose, because the whole story is about asking a
host a question.
"""

import json
import re
from pathlib import Path

import pytest

from axiom import backend, config, main, models, terminal
from conftest import StubBackend, feed, listed, row_for


HOST = "http://localhost:11434"
OTHER = "http://gpu-box:11434"

# The order a real host answers in: `modified_at` descending, measured against
# the local Ollama. Deliberately not alphabetical - a stub already in sorted
# order could not tell a sorting implementation from no implementation at all.
AS_THE_HOST_GIVES_THEM = [
    "gemma2:2b",
    "qwen2.5-coder:7b",
    "gemma4:e2b",
    "ornith:9b",
    "qwen2.5:7b",
]
SORTED = ("gemma2:2b", "gemma4:e2b", "ornith:9b", "qwen2.5-coder:7b", "qwen2.5:7b")


@pytest.fixture
def choice(tmp_path, monkeypatch):
    """A remembered-choice file of this test's own, never the repo's."""
    where = tmp_path / ".axiom" / "model.json"
    monkeypatch.setattr(models, "DEFAULT_CHOICE_FILE", where)
    return where


def run(capsys, monkeypatch, typed=None, tty=True, argv=None, **stub):
    """One run of axiom, with the terminal's answers scripted."""
    monkeypatch.setattr("sys.stdin.isatty", lambda: tty)
    feed(monkeypatch, [*(typed or []), "/exit"])
    main(argv or [], using=StubBackend(**stub))
    return capsys.readouterr()


# --- The list -----------------------------------------------------------


def test_the_list_is_numbered_and_names_every_installed_model(
    capsys, monkeypatch, choice
):
    """AC 3, AC 4, AC 5, AC 7."""
    out = run(capsys, monkeypatch, typed=["1"], models=AS_THE_HOST_GIVES_THEM)

    assert f"models on {HOST}" in out.out
    for number, model in enumerate(SORTED, start=1):
        assert f"{number}. {model}" in out.out
    # Full names, tags included - never a bare family.
    assert "qwen2.5:7b" in out.out


def test_the_list_holds_nothing_the_host_did_not_report(capsys, monkeypatch, choice):
    """AC 4. Notably not axiom's old default, which no longer exists."""
    out = run(capsys, monkeypatch, typed=["1"], models=["alpha:1b", "beta:2b"])

    assert "alpha:1b" in out.out
    assert "beta:2b" in out.out
    assert "qwen2.5:7b" not in out.out


def test_the_order_does_not_follow_the_host(capsys, monkeypatch, choice):
    """AC 6, and the reason it exists.

    Ollama answers newest-modified first, so `ollama pull` renumbers the list
    and a user picking "2" from memory gets a different model than yesterday.
    Handing the stub the host's real order is what makes this test able to
    fail: a stub already sorted would pass against an implementation that did
    no sorting whatsoever.
    """
    out = run(capsys, monkeypatch, typed=["1"], models=AS_THE_HOST_GIVES_THEM)

    assert listed(out.out) == list(SORTED)


def test_the_same_models_number_the_same_way_whatever_order_the_host_gives(
    capsys, monkeypatch, choice
):
    """AC 6. Two different host orders, one displayed order."""
    first = run(capsys, monkeypatch, typed=["1"], models=AS_THE_HOST_GIVES_THEM)
    second = run(capsys, monkeypatch, typed=["1"], models=list(reversed(SORTED)))

    # `listed`, not a line filter of its own. The filter that was here keyed on
    # "the line starts with a digit", and #77 put the list inside a border - so
    # it matched nothing in either run and the comparison passed as `[] == []`,
    # green while checking nothing at all.
    assert listed(first.out) == listed(second.out) == list(SORTED)


def test_sorting_is_case_insensitive():
    """AC 6. Capitalisation must not split the ordering."""
    assert models.sorted_models(["Zeta:1b", "alpha:1b", "Beta:1b"]) == (
        "alpha:1b",
        "Beta:1b",
        "Zeta:1b",
    )


# --- Choosing -----------------------------------------------------------


def test_a_number_starts_the_session_with_that_model(capsys, monkeypatch, choice):
    """AC 8."""
    out = run(capsys, monkeypatch, typed=["3"], models=AS_THE_HOST_GIVES_THEM)

    assert f"axiom: {SORTED[2]} at {HOST}" in out.out


def test_the_first_entry_is_the_default_until_something_is_chosen(
    capsys, monkeypatch, choice
):
    """AC 11."""
    out = run(capsys, monkeypatch, typed=["1"], models=AS_THE_HOST_GIVES_THEM)

    assert row_for(out.out, SORTED[0]).endswith("(default)")


def test_an_empty_line_takes_the_default(capsys, monkeypatch, choice):
    """AC 9."""
    out = run(capsys, monkeypatch, typed=[""], models=AS_THE_HOST_GIVES_THEM)

    assert f"axiom: {SORTED[0]} at {HOST}" in out.out


def test_a_line_of_only_spaces_counts_as_empty(capsys, monkeypatch, choice):
    """AC 9."""
    out = run(capsys, monkeypatch, typed=["   "], models=AS_THE_HOST_GIVES_THEM)

    assert f"axiom: {SORTED[0]} at {HOST}" in out.out


def test_the_chosen_model_is_what_the_session_uses(capsys, monkeypatch, choice):
    """AC 10. The startup line, the context and the tool verdict all follow it."""
    stub = StubBackend(
        info={"qwen2.context_length": 4096}, models=AS_THE_HOST_GIVES_THEM
    )
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    feed(monkeypatch, ["4", "hello", "/exit"])
    main([], using=stub)
    out = capsys.readouterr()

    assert f"axiom: {SORTED[3]} at {HOST}" in out.out
    # And it is the model actually streamed against, not merely announced.
    assert stub.streamed


def test_nothing_starts_before_a_model_is_settled(
    capsys, monkeypatch, choice, tmp_path
):
    """AC 1. No server is launched while the question is still open.

    Driven with a server that really is attempted, so there is an observable
    event to order against. Asserting only that the startup line comes later
    would pass for an implementation that started every server first and
    merely printed in a tidy order.
    """
    servers = tmp_path / "mcp.json"
    servers.write_text(
        json.dumps({"mcpServers": {"probe": {"command": "definitely-not-a-program"}}}),
        encoding="utf-8",
    )
    out = run(
        capsys,
        monkeypatch,
        typed=["1"],
        models=AS_THE_HOST_GIVES_THEM,
        argv=["--mcp-file", str(servers)],
    )

    # The server is really attempted, so its absence before the question means
    # it had genuinely not been tried yet - not that it was never tried at all.
    assert "probe" in out.err
    asked = out.out.index("which model?")
    assert "starting 1 MCP server" not in out.out[:asked]
    assert "starting 1 MCP server" in out.out[asked:]


def test_the_context_and_tools_belong_to_the_chosen_model(capsys, monkeypatch, choice):
    """AC 29. The backend must be interrogated about the model in use.

    The failure this catches is asking `model_info` and `supports_tools` about
    whatever the user named - or about some default - while announcing the one
    that was picked. Both readings print an identical startup line, so only the
    name the backend was handed can tell them apart.
    """
    stub = StubBackend(models=AS_THE_HOST_GIVES_THEM)
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    feed(monkeypatch, ["4", "hello", "/exit"])
    main([], using=stub)

    assert stub.asked_about
    assert set(stub.asked_about) == {SORTED[3]}


def test_a_named_model_is_the_one_the_backend_is_asked_about(
    capsys, monkeypatch, choice
):
    """AC 29, by the other route in."""
    stub = StubBackend(models=AS_THE_HOST_GIVES_THEM)
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    feed(monkeypatch, ["hello", "/exit"])
    main(["--model", "ornith:9b"], using=stub)

    assert set(stub.asked_about) == {"ornith:9b"}


def test_a_missing_named_model_is_never_asked_about(capsys, monkeypatch, choice):
    """AC 20, AC 29. The fallback must not leave the old name in play."""
    stub = StubBackend(models=AS_THE_HOST_GIVES_THEM)
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    feed(monkeypatch, ["2", "hello", "/exit"])
    main(["--model", "absent:70b"], using=stub)

    assert "absent:70b" not in stub.asked_about
    assert set(stub.asked_about) == {SORTED[1]}


# --- Not being asked ----------------------------------------------------


def test_a_named_installed_model_is_used_without_a_list(capsys, monkeypatch, choice):
    """AC 16."""
    out = run(
        capsys,
        monkeypatch,
        models=AS_THE_HOST_GIVES_THEM,
        argv=["--model", "ornith:9b"],
    )

    assert "which model?" not in out.out
    assert "models on" not in out.out
    assert f"axiom: ornith:9b at {HOST}" in out.out


def test_one_installed_model_is_chosen_without_a_question(capsys, monkeypatch, choice):
    """AC 17."""
    out = run(capsys, monkeypatch, models=["solo:1b"])

    assert "which model?" not in out.out
    assert "using solo:1b - the only model installed" in out.out
    assert f"axiom: solo:1b at {HOST}" in out.out


def test_not_a_terminal_is_never_asked_and_takes_the_first(capsys, monkeypatch, choice):
    """AC 18, AC 19."""
    out = run(capsys, monkeypatch, tty=False, models=AS_THE_HOST_GIVES_THEM)

    assert "which model?" not in out.out
    assert f"using {SORTED[0]} - first installed, nothing was chosen" in out.out


def test_a_piped_message_is_never_eaten_by_the_question(capsys, monkeypatch, choice):
    """AC 18. The first line has to reach the model, not answer a menu."""
    stub = StubBackend(models=AS_THE_HOST_GIVES_THEM)
    monkeypatch.setattr("sys.stdin.isatty", lambda: False)
    feed(monkeypatch, ["what is 2+2?", "/exit"])
    main([], using=stub)

    sent = stub.streamed[0]
    assert any(m.get("content") == "what is 2+2?" for m in sent)


def test_not_a_terminal_prefers_what_was_remembered(capsys, monkeypatch, choice):
    """AC 19."""
    choice.parent.mkdir(parents=True)
    choice.write_text(json.dumps({HOST: "ornith:9b"}), encoding="utf-8")

    out = run(capsys, monkeypatch, tty=False, models=AS_THE_HOST_GIVES_THEM)

    assert "using ornith:9b - your last choice here" in out.out


# --- Remembering --------------------------------------------------------


def test_a_pick_is_remembered_and_marked_next_time(capsys, monkeypatch, choice):
    """AC 10, AC 14 - the positive the four negatives below depend on."""
    run(capsys, monkeypatch, typed=["3"], models=AS_THE_HOST_GIVES_THEM)

    assert json.loads(choice.read_text(encoding="utf-8")) == {HOST: SORTED[2]}

    out = run(capsys, monkeypatch, typed=[""], models=AS_THE_HOST_GIVES_THEM)
    assert row_for(out.out, SORTED[2]).endswith("(default)")
    assert f"axiom: {SORTED[2]} at {HOST}" in out.out


def test_the_choice_is_remembered_per_host(capsys, monkeypatch, choice):
    """AC 12. Choosing against one host does not touch another."""
    run(capsys, monkeypatch, typed=["3"], models=AS_THE_HOST_GIVES_THEM)
    run(
        capsys,
        monkeypatch,
        typed=["2"],
        models=AS_THE_HOST_GIVES_THEM,
        argv=["--host", OTHER],
    )

    assert json.loads(choice.read_text(encoding="utf-8")) == {
        HOST: SORTED[2],
        OTHER: SORTED[1],
    }

    out = run(capsys, monkeypatch, typed=[""], models=AS_THE_HOST_GIVES_THEM)
    assert row_for(out.out, SORTED[2]).endswith("(default)")


def test_the_choice_lives_beside_the_mcp_config():
    """AC 13. Per directory, in `.axiom/`, and a different file from `mcp.json`.

    Read from the source rather than from the module attribute, because the
    autouse fixture that keeps every other test off the real file has by
    definition replaced that attribute. Asserting the patched value would make
    this test agree with whatever the fixture happened to set.
    """
    source = Path(models.__file__).read_text(encoding="utf-8")
    assert 'DEFAULT_CHOICE_FILE = Path(".axiom") / "model.json"' in source

    # Relative, so it is per directory rather than one file for the machine.
    assert not Path(".axiom", "model.json").is_absolute()
    assert Path(".axiom", "model.json") != config.DEFAULT_MCP_FILE
    assert Path(".axiom", "model.json").parent == config.DEFAULT_MCP_FILE.parent


def test_a_different_directory_has_its_own_remembered_choice(
    capsys, monkeypatch, tmp_path
):
    """AC 13, as behaviour rather than as a path shape.

    The path-shape test above says the constant is relative. This says the
    consequence the criterion actually claims: two directories, two choices,
    neither visible from the other.
    """
    here, there = tmp_path / "here", tmp_path / "there"
    here.mkdir()
    there.mkdir()

    monkeypatch.chdir(here)
    monkeypatch.setattr(models, "DEFAULT_CHOICE_FILE", Path(".axiom") / "model.json")
    run(capsys, monkeypatch, typed=["3"], models=AS_THE_HOST_GIVES_THEM)

    monkeypatch.chdir(there)
    out = run(capsys, monkeypatch, typed=["1"], models=AS_THE_HOST_GIVES_THEM)

    # Nothing carried over: the second directory starts with no choice at all.
    assert row_for(out.out, SORTED[0]).endswith("(default)")
    assert json.loads((here / ".axiom" / "model.json").read_text()) == {HOST: SORTED[2]}
    assert json.loads((there / ".axiom" / "model.json").read_text()) == {
        HOST: SORTED[0]
    }


def test_the_remembered_choice_is_gitignored_but_the_mcp_config_is_not():
    """AC 13's consequence. `mcp.json` is designed to be committed."""
    ignored = Path(models.__file__).parents[2] / ".gitignore"
    lines = ignored.read_text(encoding="utf-8").split()

    assert ".axiom/model.json" in lines
    assert ".axiom/" not in lines
    assert ".axiom" not in lines


def test_a_named_model_is_never_remembered(capsys, monkeypatch, choice):
    """AC 14, negative one."""
    run(
        capsys,
        monkeypatch,
        models=AS_THE_HOST_GIVES_THEM,
        argv=["--model", "ornith:9b"],
    )

    assert not choice.exists()


def test_an_environment_model_is_never_remembered(capsys, monkeypatch, choice):
    """AC 14, negative two."""
    monkeypatch.setenv("AXIOM_MODEL", "ornith:9b")

    run(capsys, monkeypatch, models=AS_THE_HOST_GIVES_THEM)

    assert not choice.exists()


def test_the_single_model_case_is_never_remembered(capsys, monkeypatch, choice):
    """AC 14, negative three."""
    run(capsys, monkeypatch, models=["solo:1b"])

    assert not choice.exists()


def test_the_non_terminal_fallback_is_never_remembered(capsys, monkeypatch, choice):
    """AC 14, negative four."""
    run(capsys, monkeypatch, tty=False, models=AS_THE_HOST_GIVES_THEM)

    assert not choice.exists()


def test_a_flag_does_not_overwrite_what_was_already_remembered(
    capsys, monkeypatch, choice
):
    """AC 14. The strongest form: a flag must not disturb an existing choice."""
    run(capsys, monkeypatch, typed=["3"], models=AS_THE_HOST_GIVES_THEM)
    run(
        capsys,
        monkeypatch,
        models=AS_THE_HOST_GIVES_THEM,
        argv=["--model", "gemma2:2b"],
    )

    assert json.loads(choice.read_text(encoding="utf-8")) == {HOST: SORTED[2]}


def test_leaving_the_list_remembers_nothing(capsys, monkeypatch, choice):
    """AC 36, AC 37."""
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    feed(monkeypatch, [EOFError()])
    main([], using=StubBackend(models=AS_THE_HOST_GIVES_THEM))

    assert not choice.exists()


def test_a_remembered_model_that_has_gone_is_said_and_not_used(
    capsys, monkeypatch, choice
):
    """AC 15."""
    choice.parent.mkdir(parents=True)
    choice.write_text(json.dumps({HOST: "removed:9b"}), encoding="utf-8")

    out = run(capsys, monkeypatch, typed=[""], models=AS_THE_HOST_GIVES_THEM)

    assert "removed:9b" in out.err
    assert "no longer has it" in out.err
    assert row_for(out.out, SORTED[0]).endswith("(default)")


# --- A named model the host does not have -------------------------------


def test_a_named_model_that_is_missing_is_reported_then_the_list_is_shown(
    capsys, monkeypatch, choice
):
    """AC 20, AC 21."""
    out = run(
        capsys,
        monkeypatch,
        typed=["2"],
        models=AS_THE_HOST_GIVES_THEM,
        argv=["--model", "absent:70b"],
    )

    assert f"absent:70b is not installed on {HOST}" in out.err
    assert "models on" in out.out
    assert f"axiom: {SORTED[1]} at {HOST}" in out.out


def test_a_named_model_that_is_missing_never_becomes_the_session(
    capsys, monkeypatch, choice
):
    """AC 20."""
    out = run(
        capsys,
        monkeypatch,
        typed=["2"],
        models=AS_THE_HOST_GIVES_THEM,
        argv=["--model", "absent:70b"],
    )

    assert f"axiom: absent:70b at {HOST}" not in out.out


def test_a_missing_named_model_falls_through_to_first_when_not_a_terminal(
    capsys, monkeypatch, choice
):
    """AC 21, the non-terminal half."""
    out = run(
        capsys,
        monkeypatch,
        tty=False,
        models=AS_THE_HOST_GIVES_THEM,
        argv=["--model", "absent:70b"],
    )

    assert "absent:70b is not installed" in out.err
    assert f"using {SORTED[0]} - first installed" in out.out


@pytest.mark.parametrize(
    ("kwargs", "typed", "expected"),
    [
        ({"models": ["solo:1b"]}, [], "solo:1b"),
        ({"models": AS_THE_HOST_GIVES_THEM, "tty": False}, [], SORTED[0]),
        ({"models": AS_THE_HOST_GIVES_THEM}, ["2"], SORTED[1]),
    ],
)
def test_the_settled_model_is_always_named_on_screen(
    capsys, monkeypatch, choice, kwargs, typed, expected
):
    """AC 22. Whichever route settled it, the user saw it."""
    out = run(capsys, monkeypatch, typed=typed, **kwargs)

    assert expected in out.out


# --- Getting it wrong ---------------------------------------------------


def test_a_number_outside_the_list_is_refused_with_the_range(
    capsys, monkeypatch, choice
):
    """AC 23."""
    out = run(capsys, monkeypatch, typed=["9", "2"], models=AS_THE_HOST_GIVES_THEM)

    assert "there is no model 9" in out.err
    assert "1 to 5" in out.err
    assert f"axiom: {SORTED[1]} at {HOST}" in out.out


def test_something_that_is_not_a_number_is_refused(capsys, monkeypatch, choice):
    """AC 24."""
    out = run(capsys, monkeypatch, typed=["ornith", "2"], models=AS_THE_HOST_GIVES_THEM)

    assert "is not a number" in out.err
    assert f"axiom: {SORTED[1]} at {HOST}" in out.out


def test_a_refusal_starts_no_session_and_remembers_nothing(capsys, monkeypatch, choice):
    """AC 23."""
    run(capsys, monkeypatch, typed=["9", "0", "x", "1"], models=AS_THE_HOST_GIVES_THEM)

    assert json.loads(choice.read_text(encoding="utf-8")) == {HOST: SORTED[0]}


def test_three_refusals_then_a_valid_number_starts_the_session(
    capsys, monkeypatch, choice
):
    """AC 25, as written."""
    out = run(
        capsys,
        monkeypatch,
        typed=["9", "nope", "0", "4"],
        models=AS_THE_HOST_GIVES_THEM,
    )

    assert out.err.count("type a number from 1 to 5") == 3
    assert f"axiom: {SORTED[3]} at {HOST}" in out.out


def test_zero_is_refused(capsys, monkeypatch, choice):
    """AC 23. The list starts at 1, so 0 names nothing."""
    out = run(capsys, monkeypatch, typed=["0", "1"], models=AS_THE_HOST_GIVES_THEM)

    assert "there is no model 0" in out.err


# --- Configuration and visibility ---------------------------------------


def test_the_flag_beats_the_environment_variable(capsys, monkeypatch, choice):
    """AC 26. The precedence is unchanged."""
    monkeypatch.setenv("AXIOM_MODEL", "gemma2:2b")

    out = run(
        capsys,
        monkeypatch,
        models=AS_THE_HOST_GIVES_THEM,
        argv=["--model", "ornith:9b"],
    )

    assert f"axiom: ornith:9b at {HOST}" in out.out


def test_help_says_what_happens_with_no_model_named(capsys):
    """AC 27."""
    with pytest.raises(SystemExit):
        config.parse_args(["--help"])

    printed = capsys.readouterr().out
    assert "lists the models installed" in printed


def test_the_new_folder_is_announced_once(capsys, monkeypatch, choice):
    """AC 30. Said the first time, silent afterwards."""
    first = run(capsys, monkeypatch, typed=["2"], models=AS_THE_HOST_GIVES_THEM)
    assert "remembering this choice in" in first.out

    second = run(capsys, monkeypatch, typed=["3"], models=AS_THE_HOST_GIVES_THEM)
    assert "remembering this choice in" not in second.out


# --- Failure ------------------------------------------------------------


def test_an_unreachable_host_says_so_and_exits_non_zero(capsys, monkeypatch, choice):
    """AC 31. The status is measured, not the message alone."""
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    stub = StubBackend(listing=backend.ConnectionLost("refused"))

    with pytest.raises(SystemExit) as leaving:
        main([], using=stub)

    assert leaving.value.code == 2
    out = capsys.readouterr()
    assert f"cannot reach Ollama at {HOST}" in out.err
    assert "models on" not in out.out
    assert "which model?" not in out.out


def test_a_host_with_no_models_says_so_and_exits_non_zero(capsys, monkeypatch, choice):
    """AC 32. Distinct from unreachable, with advice the user can act on."""
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)

    with pytest.raises(SystemExit) as leaving:
        main([], using=StubBackend(models=[]))

    assert leaving.value.code == 2
    out = capsys.readouterr()
    assert "has no models installed" in out.err
    assert "ollama pull" in out.err
    assert "which model?" not in out.out


def test_the_two_failures_do_not_read_the_same(capsys, monkeypatch, choice):
    """AC 31 against AC 32. Two states, two messages."""
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)

    with pytest.raises(SystemExit):
        main([], using=StubBackend(listing=backend.ConnectionLost("refused")))
    unreachable = capsys.readouterr().err

    with pytest.raises(SystemExit):
        main([], using=StubBackend(models=[]))
    empty = capsys.readouterr().err

    assert unreachable != empty


def test_a_failure_to_list_prints_nothing_that_reads_as_a_reply(
    capsys, monkeypatch, choice
):
    """AC 35."""
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)

    with pytest.raises(SystemExit):
        main([], using=StubBackend(listing=backend.ConnectionLost("refused")))

    out = capsys.readouterr()
    assert out.out == ""


def test_a_broken_choice_file_is_said_and_the_session_carries_on(
    capsys, monkeypatch, choice
):
    """AC 33."""
    choice.parent.mkdir(parents=True)
    choice.write_text("{ not json at all", encoding="utf-8")

    out = run(capsys, monkeypatch, typed=["2"], models=AS_THE_HOST_GIVES_THEM)

    # Names the file, because that is the only thing the user can act on - and
    # says nothing about the host, which has done nothing wrong. An earlier
    # version of this reused the "your last choice has gone" wording and
    # produced "your saved choice was your last choice here but <host> no
    # longer has it", which blamed the host for a corrupt local file. The test
    # then asserted only that "saved choice" appeared, and passed on it.
    assert str(choice) in out.err
    assert "could not be read" in out.err
    assert "no longer has it" not in out.err
    assert f"axiom: {SORTED[1]} at {HOST}" in out.out


def test_a_choice_that_cannot_be_saved_still_starts_the_session(
    capsys, monkeypatch, choice
):
    """AC 34. The pick costs the remembering, never the session."""

    def refuse(*args, **kwargs):
        raise OSError("read-only file system")

    monkeypatch.setattr(Path, "mkdir", refuse)

    out = run(capsys, monkeypatch, typed=["2"], models=AS_THE_HOST_GIVES_THEM)

    assert "could not remember this choice" in out.err
    assert f"axiom: {SORTED[1]} at {HOST}" in out.out


def test_a_bad_choice_file_is_replaced_rather_than_stranding_the_user(choice):
    """AC 33, AC 34. A corrupt file must not make every later save fail."""
    choice.parent.mkdir(parents=True)
    choice.write_text("]] broken [[", encoding="utf-8")

    assert models.write_choice("ornith:9b", HOST) is None
    assert json.loads(choice.read_text(encoding="utf-8")) == {HOST: "ornith:9b"}


# --- Leaving ------------------------------------------------------------


@pytest.mark.parametrize("leaving", [EOFError(), KeyboardInterrupt()])
def test_leaving_the_list_exits_zero_without_a_session(
    capsys, monkeypatch, choice, leaving
):
    """AC 36, AC 37."""
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    stub = StubBackend(models=AS_THE_HOST_GIVES_THEM)
    feed(monkeypatch, [leaving])

    main([], using=stub)  # returns normally: status 0

    assert stub.streamed == []
    assert f"axiom: {SORTED[0]} at" not in capsys.readouterr().out


def test_the_question_is_asked_once_and_not_again(capsys, monkeypatch, choice):
    """AC 38. Settled once, and it stays settled for the run."""
    out = run(
        capsys,
        monkeypatch,
        typed=["2", "hello", "and again"],
        models=AS_THE_HOST_GIVES_THEM,
    )

    assert out.out.count("which model?") == 1
    assert out.out.count("models on") == 1


# --- #77: the list inside a border ----------------------------------------


def raw_row(text, model):
    """The chooser's row for `model` with its escape sequences still on it."""
    for line in text.splitlines():
        if model in re.sub(r"\x1b\[[0-9;]*m", "", line):
            return line
    return ""


def annotation_column(text, model):
    """Where this row's annotation starts, counting from the model's number.

    Measured from the number rather than from the left edge, so the border and
    the padding around the list are not what is being compared - AC 2 is about
    the annotations lining up with each other.

    The end of the first run of two-or-more spaces, not `split("  ")[0]`. The
    first version used the split and measured **the end of the name** instead,
    which differs by a character between `gemma2:2b` and `gemma4:e2b` whatever
    the padding does - so it reported a stagger on a list that was aligned.
    """
    bare = row_for(text, model)
    gap = re.search(r"\s{2,}", bare)
    return gap.end() if gap else None


def test_the_list_is_drawn_inside_a_border_naming_the_host(capsys, monkeypatch, choice):
    """#77 AC 1."""
    out = run(capsys, monkeypatch, typed=["1"], models=AS_THE_HOST_GIVES_THEM)

    assert "╭" in out.out and "╰" in out.out, "no border around the list"
    assert f"models on {HOST}" in out.out, "the host is not named on the list"
    for number, model in enumerate(SORTED, start=1):
        assert row_for(out.out, model).startswith(f"{number}. ")


def test_every_annotation_begins_at_the_same_column(capsys, monkeypatch, choice):
    """#77 AC 2. The point of padding the names to the longest.

    `gemma2:2b` and `qwen2.5-coder:7b` differ by seven characters, so a list that
    does not pad staggers every annotation by the length of the name above it.
    """
    out = run(
        capsys,
        monkeypatch,
        typed=["1"],
        models=AS_THE_HOST_GIVES_THEM,
        capable={m: m in {"gemma4:e2b", "ornith:9b"} for m in SORTED},
    )

    columns = {
        annotation_column(out.out, model)
        for model in SORTED
        if annotation_column(out.out, model) is not None
    }
    assert len(columns) == 1, f"annotations start at {sorted(columns)}"


def test_the_marked_model_is_dressed_unlike_the_others(capsys, monkeypatch, choice):
    """#77 AC 3. "Which one it is can be seen without reading every row."

    A marker only the reader's eye can find by reading each line is not a marker.
    The name itself is accented, so the row differs before it is read.

    **`sys.stdout.isatty` has to be forced here**, and finding that out was worth
    the test on its own: under pytest stdout is captured, the panel's Console sees
    no terminal and emits the box with no colour at all. Which is right - a
    redirected run should not be full of escapes - but it means every other test
    in this file is looking at an uncoloured chooser, and a criterion about how
    something is *dressed* cannot be checked from one of those.
    """
    monkeypatch.setattr("sys.stdout.isatty", lambda: True)
    out = run(capsys, monkeypatch, typed=["1"], models=AS_THE_HOST_GIVES_THEM)

    marked = raw_row(out.out, SORTED[0])
    plain = raw_row(out.out, SORTED[1])

    assert marked and plain
    assert re.findall(r"\x1b\[[0-9;]*m", marked) != re.findall(
        r"\x1b\[[0-9;]*m", plain
    ), "the marked row is dressed exactly like an unmarked one"


@pytest.mark.parametrize(
    "able, annotated",
    [
        ({"gemma4:e2b", "ornith:9b"}, True),
        (set(SORTED), False),
        (set(), False),
    ],
    ids=["some capable", "all capable", "none capable"],
)
def test_tools_are_annotated_only_where_they_explain_something(
    capsys, monkeypatch, choice, able, annotated
):
    """#77 AC 4, at all three hosts rather than the interesting one.

    The middle and the last are where a marker appears that should not: on a host
    where every model can call tools, or none can, the order is plain name order
    and a note on every row explains nothing.
    """
    out = run(
        capsys,
        monkeypatch,
        typed=["1"],
        models=AS_THE_HOST_GIVES_THEM,
        capable={m: m in able for m in SORTED},
    )

    # The rows, not the whole run. `"tools" in out.out` also matches the startup
    # line - `no tools - this model cannot call them` - so it read as annotated
    # on precisely the host where nothing should be annotated.
    rows = [row_for(out.out, model) for model in SORTED]
    assert any("tools" in row for row in rows) is annotated


def test_a_narrow_window_still_shows_every_name_in_full(capsys, monkeypatch, choice):
    """#77 AC 6.

    A panel spends columns the plain list did not: two on the border and four on
    the padding. At **20** columns there are fourteen left, `qwen2.5-coder:7b` is
    sixteen, and the name has to wrap - which is the case that crops if anything
    does. 30 was the first width tried here and nothing was squeezed at all: every
    name fit, so the test passed while the renderer was told never to wrap.

    **The border glyphs have to come out along with the whitespace.** A wrapped
    name arrives as `qwen2.5-coder:` and `7b` on two rows with a `│` between them,
    and a check that removes only spaces reads that as a crop. Wrapping in full is
    the criterion being met; losing characters is not.
    """
    monkeypatch.setattr(terminal, "_width", lambda: 20)
    out = run(capsys, monkeypatch, typed=["1"], models=AS_THE_HOST_GIVES_THEM)

    plain = re.sub(r"\x1b\[[0-9;]*m", "", out.out)
    flat = re.sub(r"[\s│╭╮╰╯─]+", "", plain)
    for model in SORTED:
        assert model in flat, f"{model} lost characters at 20 columns"

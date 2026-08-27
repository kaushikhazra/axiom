"""The line after a switch carries the same facts as the line at startup.

The criterion is that two lines **agree**, so these tests compare them against
each other rather than against hard-coded wording. A test that spelled out the
expected text on both sides would drift with them and catch nothing - and drift
is exactly what produced this row. `announce()` and `note_switched()` built
their phrasings independently, and the web state and the debug-override note
went missing from one and not the other.

Every fact is exercised at **two settings**. Printing "web off" once shows the
word can be printed; only web-on beside web-off shows it follows anything.
"""

import re

import pytest

from axiom import main, models
from conftest import StubBackend, feed


INSTALLED = ["big:70b", "small:1b"]
WINDOWS = {
    "big:70b": {"a.context_length": 32768},
    "small:1b": {"a.context_length": 4096},
}


@pytest.fixture(autouse=True)
def choice(tmp_path, monkeypatch):
    monkeypatch.setattr(
        models, "DEFAULT_CHOICE_FILE", tmp_path / ".axiom" / "model.json"
    )


def run(capsys, monkeypatch, argv, typed=("/model small:1b",), **stub):
    stub.setdefault("models", INSTALLED)
    stub.setdefault("infos", WINDOWS)
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    made = StubBackend(**stub)
    feed(monkeypatch, [*typed, "/exit"])
    main([*argv, "--model", "big:70b"], using=made)
    return made, capsys.readouterr()


def facts(line: str) -> dict:
    """The facts a session line reports, parsed out of its parenthesis.

    Both lines share the shape `... (context: <room>, <what it can do>)`, so
    one parser reads both - which is itself part of the point. What comes
    before the parenthesis differs (`<model> at <host>` against `now <model>`)
    and is not a fact about the session's capabilities.
    """
    inside = re.search(r"\(context: (.*)\)\s*$", line.strip())
    assert inside, f"not a session line: {line!r}"
    room, _, can_do = inside.group(1).partition(", ")
    # `room` may itself carry the override note, which uses the same separator.
    override = "debug override" in inside.group(1)
    if override:
        room = room.replace(", debug override", "")
        can_do = can_do.replace("debug override, ", "")
    return {
        "override": override,
        "web": (
            "on"
            if "including web" in can_do
            else "off"
            if "web off" in can_do
            else None
        ),
        "tools": can_do.replace(" including web", "").replace(", web off", ""),
        "room": room,
    }


def both(out: str) -> tuple[dict, dict]:
    """The startup line's facts and the switch line's, from one run."""
    lines = out.splitlines()
    start = next(line for line in lines if " at http" in line)
    switch = next(line for line in lines if "now " in line and "context:" in line)
    return facts(start), facts(switch)


# --- The two facts that went missing ------------------------------------


@pytest.mark.parametrize(
    ("argv", "expected"), [([], "on"), (["--no-web"], "off")], ids=["web on", "web off"]
)
def test_the_switch_line_reports_the_web_state(capsys, monkeypatch, argv, expected):
    """AC 1, AC 7, AC 10. Two settings, or this proves only that a word prints."""
    _, out = run(capsys, monkeypatch, argv)
    started, switched = both(out.out)

    assert started["web"] == expected
    assert switched["web"] == expected, "the switch line dropped the web state"


def test_the_web_state_is_knowable_from_the_switch_line_alone(capsys, monkeypatch):
    """AC 10. A tool count is not a web state.

    Two runs whose switch lines must differ. Before this row both said
    `N tools` and the only hint was the count itself - which requires knowing
    what the count would have been otherwise.
    """
    _, on = run(capsys, monkeypatch, [])
    _, off = run(capsys, monkeypatch, ["--no-web"])

    assert both(on.out)[1]["web"] != both(off.out)[1]["web"]


@pytest.mark.parametrize(
    ("env", "expected"),
    [(None, False), ("3000", True)],
    ids=["no override", "override"],
)
def test_the_switch_line_reports_the_debug_override(capsys, monkeypatch, env, expected):
    """AC 2, AC 8."""
    if env:
        monkeypatch.setenv("AXIOM_DEBUG_MAX_CONTEXT", env)

    _, out = run(capsys, monkeypatch, [])
    started, switched = both(out.out)

    assert started["override"] is expected
    assert switched["override"] is expected, "the switch line dropped the override note"


def test_a_forced_context_is_never_shown_as_the_models_own(capsys, monkeypatch):
    """AC 9, and the purpose behind AC 2.

    The more damaging of the two gaps: `3000 tokens` after a switch reads as
    the new model's real window, and it is the exact figure someone debugging
    a compaction problem would reason from.
    """
    monkeypatch.setenv("AXIOM_DEBUG_MAX_CONTEXT", "3000")
    _, forced = run(capsys, monkeypatch, [])
    monkeypatch.delenv("AXIOM_DEBUG_MAX_CONTEXT")
    _, natural = run(capsys, monkeypatch, [])

    assert both(forced.out)[1] != both(natural.out)[1]
    assert both(forced.out)[1]["override"] is True
    assert both(natural.out)[1]["override"] is False


# --- The two lines agree ------------------------------------------------


@pytest.mark.parametrize(
    ("argv", "stub", "env"),
    [
        ([], {}, None),
        (["--no-web"], {}, None),
        (["--no-tools"], {}, None),
        ([], {"capable": {"big:70b": True, "small:1b": False}}, None),
        ([], {}, "3000"),
    ],
    ids=["web on", "web off", "tools off", "cannot call tools", "override"],
)
def test_the_switch_line_agrees_with_the_startup_line(
    capsys, monkeypatch, argv, stub, env
):
    """AC 5, AC 6, AC 7, AC 8 - every state, compared line against line.

    **The comparison is switching *to* a model against starting *on* it**, not
    the two lines of one run. Those describe different models, and two models
    may legitimately differ - a model that cannot call tools has nothing to say
    about the web, whatever the model before it could do. The criterion is that
    a given state reads the same whichever line reports it.

    Never against hard-coded wording. If the two are ever phrased differently
    for the same state, this fails whatever the phrasing became.
    """
    if env:
        monkeypatch.setenv("AXIOM_DEBUG_MAX_CONTEXT", env)

    _, switching = run(capsys, monkeypatch, argv, **stub)
    switched = both(switching.out)[1]

    # The same model, reached the other way: named at launch, so its facts are
    # reported by the startup line instead.
    stub.setdefault("models", INSTALLED)
    stub.setdefault("infos", WINDOWS)
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    feed(monkeypatch, ["/exit"])
    main([*argv, "--model", "small:1b"], using=StubBackend(**stub))
    started = facts(
        next(
            line for line in capsys.readouterr().out.splitlines() if " at http" in line
        )
    )

    assert started == switched, "the same model reads differently by which line said it"


def test_a_context_that_could_not_be_established_reads_the_same(capsys, monkeypatch):
    """AC 8. `Ollama default` is a state too, and it has its own wording."""
    _, out = run(capsys, monkeypatch, [], infos={})
    started, switched = both(out.out)

    assert started["room"] == "Ollama default"
    assert switched["room"] == "Ollama default"


def test_the_window_still_follows_the_model(capsys, monkeypatch):
    """AC 3. Agreement must not be bought by reporting a stale number.

    The expected numbers are derived from the fixture rather than written out,
    so a fixture change cannot quietly turn this into a restatement of itself.
    """
    _, out = run(capsys, monkeypatch, [])
    started, switched = both(out.out)

    assert started["room"] == f"{WINDOWS['big:70b']['a.context_length']} tokens"
    assert switched["room"] == f"{WINDOWS['small:1b']['a.context_length']} tokens", (
        "the switch reported the old window"
    )
    assert started["room"] != switched["room"]


# --- What stays off it --------------------------------------------------


def test_the_host_is_not_repeated(capsys, monkeypatch):
    """AC 11. A switch cannot change it, and the startup line already named it."""
    _, out = run(capsys, monkeypatch, [])
    switch = next(
        line for line in out.out.splitlines() if "now " in line and "context:" in line
    )

    assert "http://" not in switch


def test_nothing_else_about_a_switch_changes(capsys, monkeypatch):
    """AC 12. The conversation still carries, and the model still changes."""
    stub, out = run(
        capsys, monkeypatch, [], typed=["first", "/model small:1b", "second"]
    )

    assert stub.asked_about[-1] == "small:1b"
    contents = [m.get("content") for m in stub.streamed[-1]]
    assert "first" in contents and "second" in contents

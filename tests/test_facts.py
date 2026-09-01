"""#77 AC 7 to 16: the session's facts, and the clear that puts them at the top.

The panel is drawn **only at a terminal**. A redirected run takes the path it took
before #77, which is what AC 33 requires and what leaves the golden transcript
untouched - so every test here has to force `sys.stdout.isatty`, and one of them
checks the other half: that without a terminal nothing changes at all.
"""

import re

import pytest

from axiom import main, models, terminal
from conftest import StubBackend, feed


HOST = "http://localhost:11434"
INSTALLED = ["solo:1b"]

CLEAR = "\x1b[2J"
CLEAR_SCROLLBACK = "\x1b[3J"


@pytest.fixture
def choice(tmp_path, monkeypatch):
    monkeypatch.setattr(
        models, "DEFAULT_CHOICE_FILE", tmp_path / ".axiom" / "model.json"
    )


def at_a_terminal(monkeypatch):
    """Not a fixture, and that is the whole point.

    A fixture patches during pytest's **setup** phase, and `capsys` swaps
    `sys.stdout` again for the **call** phase - so the patch lands on an object
    that no longer exists by the time the test body runs, `isatty` reads False,
    and every assertion about the panel quietly checks the plain path instead.
    Five tests here failed that way before this was a function. `test_rendering`
    already had it as a helper for the same reason.
    """
    monkeypatch.setattr("sys.stdout.isatty", lambda: True)
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)


def plain(text: str) -> str:
    return re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", text)


def facts(**over):
    """`show_facts` with a plausible session, and whatever this test cares about."""
    settled = dict(
        model="solo:1b",
        host=HOST,
        context=32768,
        overridden=False,
        tools=11,
        web=True,
        cost=1250,
        connected={},
        problems=[],
        bounds=None,
        skills_loaded=0,
        skill_problems=[],
        skills_cost=None,
        skills_enabled=True,
        reason="",
    )
    settled.update(over)
    terminal.show_facts(**settled)


def run(capsys, monkeypatch, typed=None, **stub):
    stub.setdefault("models", INSTALLED)
    feed(monkeypatch, [*(typed or []), "/exit"])
    main([], using=StubBackend(**stub))
    return capsys.readouterr()


# --- the clear ---------------------------------------------------------------


def test_settling_on_a_model_clears_the_screen(
    capsys, monkeypatch, choice
):
    """#77 AC 7."""
    at_a_terminal(monkeypatch)
    out = run(capsys, monkeypatch)

    assert CLEAR in out.out, "the screen was never cleared"


def test_the_facts_are_the_first_thing_after_the_clear(
    capsys, monkeypatch, choice
):
    """#77 AC 8. Not merely present - present *first*.

    Asserting the panel is somewhere in the output would pass for a clear that
    happened three lines earlier with something else in between, which is the
    failure this criterion exists to stop.
    """
    at_a_terminal(monkeypatch)
    out = run(capsys, monkeypatch)
    after = plain(out.out.split(CLEAR, 1)[1]).strip()

    assert after.startswith("╭"), f"something came between: {after[:60]!r}"
    assert "axiom" in after.split("\n")[0], "the panel is not what followed"


def test_the_scrollback_is_not_cleared(capsys, monkeypatch, choice):
    """#77 AC 9.

    On the bytes rather than on the promise. `\\x1b[2J` erases the screen and
    `\\x1b[3J` also empties the scrollback buffer; the two are indistinguishable
    the moment they run and differ only in what the user can scroll back to.
    """
    at_a_terminal(monkeypatch)
    out = run(capsys, monkeypatch)

    assert CLEAR_SCROLLBACK not in out.out, "scrollback was wiped too"


def test_the_screen_is_cleared_once_and_not_again(
    capsys, monkeypatch, choice
):
    """#77 AC 10. Counted over a session with turns in it, not read off the call.

    A clear per turn would lose the conversation as it went, and would look
    perfectly correct at the call site.
    """
    at_a_terminal(monkeypatch)
    out = run(capsys, monkeypatch, typed=["hello", "and again", "once more"])

    assert out.out.count(CLEAR) == 1, f"cleared {out.out.count(CLEAR)} times"


# --- what the facts say ------------------------------------------------------


def test_the_facts_name_the_model_host_window_tools_and_cost(capsys, monkeypatch):
    """#77 AC 11."""
    at_a_terminal(monkeypatch)
    facts()
    shown = plain(capsys.readouterr().out)

    assert "solo:1b" in shown
    assert HOST in shown
    assert "32768" in shown
    assert "11 tools" in shown
    assert "1250" in shown


def test_a_fact_axiom_does_not_have_is_left_out(capsys, monkeypatch):
    """#77 AC 12, both directions.

    One direction is vacuous on its own: a panel that prints nothing at all
    satisfies "left out rather than shown as zero". So the same fact is checked
    present when it is known and absent when it is not.
    """
    at_a_terminal(monkeypatch)
    facts(cost=None)
    without = plain(capsys.readouterr().out)

    facts(cost=1250)
    with_it = plain(capsys.readouterr().out)

    assert "cost" not in without, "an unknown cost was still given a row"
    assert "0 tokens" not in without, "an unknown cost was reported as zero"
    assert "cost" in with_it, "a known cost was left out"


def test_configured_servers_are_shown_with_their_tool_counts(capsys, monkeypatch):
    """#77 AC 13."""
    at_a_terminal(monkeypatch)
    facts(connected={"filesystem": 5, "github": 12})
    shown = plain(capsys.readouterr().out)

    assert "filesystem" in shown and "5 tools" in shown
    assert "github" in shown and "12 tools" in shown


def test_skills_are_shown_with_their_number_and_cost(capsys, monkeypatch):
    """#77 AC 14, and its other half - a run with no skills says nothing."""
    at_a_terminal(monkeypatch)
    facts(skills_loaded=3, skills_cost=210)
    shown = plain(capsys.readouterr().out)

    facts(skills_loaded=0, skills_cost=None)
    silent = plain(capsys.readouterr().out)

    assert "3 skills" in shown and "210" in shown
    assert "skill" not in silent, "a run with no skills mentioned them anyway"


def test_the_reason_rides_on_the_models_row(capsys, monkeypatch):
    """#77 AC 15. "Shown with the model, not as a separate statement."

    The phrase has to be on the same row as the name. Asserting it is merely
    present would pass for the line it used to be - `axiom: using solo:1b - your
    last choice here` - which is exactly what this criterion moved.
    """
    at_a_terminal(monkeypatch)
    facts(reason="remembered")
    rows = plain(capsys.readouterr().out).splitlines()

    holding = [row for row in rows if "solo:1b" in row]
    assert holding, "no row named the model"
    assert "your last choice here" in holding[0], "the reason is on its own line"


def test_a_model_the_user_chose_is_given_no_reason(capsys, monkeypatch):
    """#77 AC 15's boundary. A choice the user made needs no explaining."""
    at_a_terminal(monkeypatch)
    facts(reason="")
    shown = plain(capsys.readouterr().out)

    assert "last choice" not in shown and "only model" not in shown


def test_what_failed_to_load_is_shown_outside_the_facts(capsys, monkeypatch):
    """#77 AC 16. Visible, and visibly not one of the facts."""
    at_a_terminal(monkeypatch)
    facts(
        problems=["github: MCP_TOKEN is not set"],
        skill_problems=["x has no description"],
    )
    got = capsys.readouterr()
    everything = plain(got.out) + plain(got.err)

    assert "MCP_TOKEN is not set" in everything
    assert "x has no description" in everything
    # Outside the border: the last row of the box comes before them.
    box_ends = plain(got.out).rindex("╰")
    assert plain(got.out).index("has no description") > box_ends


# --- the other half: no terminal, no change ----------------------------------


def test_without_a_terminal_the_facts_are_the_lines_they_always_were(
    capsys, monkeypatch
):
    """#77 AC 33, and why the golden transcript did not move.

    A redirected run must be unchanged byte for byte. This is the test that says
    the panel is genuinely gated rather than merely usually skipped.
    """
    monkeypatch.setattr("sys.stdout.isatty", lambda: False)
    facts(reason="remembered")
    shown = capsys.readouterr().out

    assert shown == (
        f"axiom: solo:1b at {HOST} (context: 32768 tokens, 11 tools including web)\n"
        "axiom: tools cost about 1250 tokens per request, 4% of the window\n"
    )
    assert "╭" not in shown and CLEAR not in shown

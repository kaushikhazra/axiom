"""#91: what the model is told about the machine it is running on and the day.

Nothing here needs a model, and that bounds what it can settle. Half of #91 is
about a model's *behaviour* - AC 1 to AC 4 are what it answers and what command
it writes, AC 7 is what it puts in a search - and a test asserting the prompt
contains the word `cmd.exe` proves a sentence was built and nothing more. Those
are settled by a live probe, recorded beside #89's in
`.claude/loop/91-machine-and-day/`.

What is settled here is everything that is a claim about axiom: that the
sentence says the truth about this machine, that the day is the local one and
is re-read rather than frozen, that every run gets it, that the cost line
accounts for it, and that it names nothing it should not.
"""

import getpass
import json
import os
import platform
import re
from datetime import datetime
from pathlib import Path

import pytest

from axiom import compaction, main, models, tools
from conftest import StubBackend, feed


@pytest.fixture(autouse=True)
def choice(tmp_path, monkeypatch):
    monkeypatch.setattr(
        models, "DEFAULT_CHOICE_FILE", tmp_path / ".axiom" / "model.json"
    )


def run(capsys, monkeypatch, argv=(), typed=(), **stub):
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    made = StubBackend(**stub)
    feed(monkeypatch, [*typed, "/exit"])
    main([*argv, "--model", "qwen2.5:7b"], using=made)
    return made, capsys.readouterr()


def standing(stub: StubBackend, turn: int = 0) -> str:
    """The system message as it was sent on a given turn.

    Read back out of what the backend received rather than rebuilt here. A
    prompt asserted by calling `system_prompt` again would agree with itself
    while the session sent something else entirely - which is the whole failure
    AC 12 and AC 9 are about.
    """
    return stub.streamed[turn][0]["content"]


class FixedClock:
    """A `datetime` module stand-in that answers with the times a test names.

    `utcnow` deliberately answers a *different* day from `now`. AC 8 is that the
    local date is the one told, and the only way to fail it is to reach for UTC
    - so the stub makes reaching for UTC produce a visibly wrong answer rather
    than the same answer by coincidence, which is what a machine sitting in UTC
    would give.
    """

    def __init__(self, local: datetime, utc: datetime) -> None:
        self._local, self._utc = local, utc

    def now(self, tz=None):  # noqa: ANN001, ARG002
        return self._local

    def utcnow(self):
        return self._utc


# --- The machine (AC 1, AC 2, AC 5) -----------------------------------------


def test_the_sentence_names_this_machines_system_and_shell():
    """AC 1 and AC 2, as far as a test can carry them.

    Derived from `platform` and `os.name` rather than written down, because a
    literal would pass on the machine it was written on and lie everywhere else
    - and the lie would be invisible: the prompt would still be built, the
    model would still answer, and it would answer about the wrong system.
    """
    said = tools.machine_and_day()

    expected = {"Darwin": "macOS"}.get(platform.system(), platform.system())
    assert expected in said
    assert ("cmd.exe" if os.name == "nt" else "/bin/sh") in said


def test_the_shell_named_is_the_one_commands_are_actually_handed_to():
    """AC 2. The claim is about `run_command`, not about a preference.

    `shell=True` is what makes this true, and it is what a future edit would
    take away - a switch to a list argv, or to an explicit executable, would
    leave this sentence describing a shell nothing runs in. Asserting the call
    keeps the prompt and the behaviour tied together the way the limits are.
    """
    source = Path(tools.__file__).read_text(encoding="utf-8")

    assert "shell=True" in source


def test_a_bare_command_runs_in_the_working_directory(tmp_path):
    """AC 3's other half: the model does not need the path, because this is true.

    The prompt deliberately does **not** say so - saying it made qwen2.5:7b
    print the command instead of calling the tool, measured four runs to two,
    and `system_prompt`'s docstring carries the table. What is left is the
    behaviour itself, asserted here so that a change to `run_command`'s cwd
    cannot quietly make the model's bare `dir` wrong.
    """
    (tmp_path / "landmark.txt").write_text("here", encoding="utf-8")
    limits = tools.Limits(working_directory=str(tmp_path))

    listed = tools.run(
        "run_command",
        {"command": 'python -c "import os; print(os.listdir())"'},
        limits,
    )

    assert "landmark.txt" in listed


def test_it_reads_as_a_fact_about_the_run_rather_than_a_setting():
    """AC 5. The same voice the limits are already given in."""
    said = tools.machine_and_day()

    assert "facts about the machine, not settings" in said


# --- The day (AC 6, AC 8, AC 9) ---------------------------------------------


def test_the_day_is_the_machines_own_date():
    """AC 6. Spelled out, rather than left for the model to infer from a number."""
    said = tools.machine_and_day(now=datetime(2026, 9, 15, 13, 45))

    assert "Tuesday 15 September 2026" in said


def test_the_day_is_the_local_one_and_not_utc(monkeypatch):
    """AC 8.

    The two differ for a few hours every day in most of the world, and by a
    whole day in exactly the case this matters: late evening east of Greenwich,
    which is where this is being written.
    """
    monkeypatch.setattr(
        tools,
        "datetime",
        FixedClock(datetime(2026, 9, 16, 1, 30), datetime(2026, 9, 15, 20, 0)),
    )
    said = tools.machine_and_day()

    assert "16 September 2026" in said
    assert "15 September 2026" not in said


class MidnightBackend(StubBackend):
    """A backend that lets the clock reach the next day between two turns.

    The move happens *after* a turn has been streamed, which is what makes the
    assertion mean anything: turn 0 was built while it was still the 15th, so a
    session that holds on to that prompt sends the 15th again on turn 1.
    """

    def __init__(self, clock: FixedClock, **stub) -> None:
        super().__init__(**stub)
        self._clock = clock

    def stream(self, model, messages, options=None, tools=None):  # noqa: ANN001
        yield from super().stream(model, messages, options=options, tools=tools)
        self._clock._local = datetime(2026, 9, 16, 0, 1)


def test_a_session_still_running_after_midnight_is_told_the_new_date(monkeypatch):
    """AC 9, and the reason the prompt is rebuilt each turn rather than held.

    A session that keeps the prompt it built at startup passes every other test
    in this file and then tells the model it is yesterday for as long as the
    window stays open - with nothing going wrong that anyone could see. That is
    the shape of defect this whole issue is about.
    """
    clock = FixedClock(datetime(2026, 9, 15, 23, 59), datetime(2026, 9, 15, 23, 59))
    monkeypatch.setattr(tools, "datetime", clock)
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    made = MidnightBackend(clock)
    feed(monkeypatch, ["what day is it?", "and now?", "/exit"])

    main(["--model", "qwen2.5:7b"], using=made)

    assert "15 September 2026" in standing(made, 0)
    assert "16 September 2026" in standing(made, 1)


# --- Every run gets it (AC 10, AC 11, AC 12) --------------------------------


def test_a_run_with_no_configuration_of_any_kind_gets_it(capsys, monkeypatch):
    """AC 10. No flag, nothing in the environment, nothing on disk."""
    made, _ = run(capsys, monkeypatch, typed=["hello"])

    assert "You are running on" in standing(made)
    assert "Today is" in standing(made)


def test_a_run_with_tools_switched_off_is_still_told(capsys, monkeypatch):
    """AC 11. The machine is not a property of having tools."""
    made, _ = run(capsys, monkeypatch, argv=["--no-tools"], typed=["hello"])

    assert "You are running on" in standing(made)
    assert "Today is" in standing(made)


def test_a_model_switched_to_mid_session_is_told_the_same(capsys, monkeypatch):
    """AC 12. The new model starts where the old one was, not from nothing."""
    made, _ = run(
        capsys,
        monkeypatch,
        typed=["hello", "/model ornith:9b", "hello again"],
        models=["qwen2.5:7b", "ornith:9b"],
    )

    assert standing(made, -1) == standing(made, 0)
    assert "You are running on" in standing(made, -1)


# --- What it costs (AC 13, AC 14) -------------------------------------------


def reported(text: str) -> int | None:
    found = re.search(r"tools cost about (\d+) tokens", text)
    return int(found.group(1)) if found else None


def test_the_reported_cost_accounts_for_what_it_says_about_the_machine(
    capsys, monkeypatch
):
    """AC 13. Weighed the way the size checks weigh it, not counted a second way."""
    _, out = run(capsys, monkeypatch)

    full = tools.system_prompt(tools.Limits())
    assert tools.machine_and_day() in full, "the cost is computed from another prompt"
    stripped = full.replace(tools.machine_and_day(), "")
    weighed = compaction.estimated_tokens([{"role": "system", "content": full}])
    lighter = compaction.estimated_tokens([{"role": "system", "content": stripped}])

    assert weighed > lighter, "the machine sentence weighed nothing"
    assert reported(out.out) >= weighed, "the figure is smaller than the prompt alone"


def test_the_reported_cost_moves_when_the_environment_text_does(capsys, monkeypatch):
    """AC 14. The figure on screen is never stale.

    Made true by there being one prompt rather than two - the environment is
    part of what `system_prompt` returns, so nothing has to remember to add it
    to the total. This lengthens it and watches the number follow.
    """
    _, before = run(capsys, monkeypatch)
    monkeypatch.setattr(tools, "machine_and_day", lambda now=None: "x" * 4000)
    _, after = run(capsys, monkeypatch)

    assert reported(after.out) > reported(before.out)


# --- What must not be in it (AC 15, AC 16) ----------------------------------


def test_nothing_it_says_names_the_user_or_their_home(capsys, monkeypatch):
    """AC 15. The obvious leak, and the one a shell prompt would carry.

    The working directory is exempt and is asserted elsewhere - the model is
    given it on purpose, and AC 16 says what must not appear is a path *other*
    than that one.
    """
    said = tools.machine_and_day()

    assert getpass.getuser().lower() not in said.lower()
    assert str(Path.home()) not in said


def test_nothing_it_says_is_the_value_of_an_environment_variable():
    """AC 15 and AC 16 together, through the one that is tempting to reach for.

    `COMSPEC` is exactly the right answer to "which shell runs my commands" and
    exactly the wrong thing to paste: it is an environment variable's value and
    a path outside the working directory, and it names the system directory of
    the machine axiom is on.
    """
    said = tools.machine_and_day()

    for value in os.environ.values():
        if len(value) > 3 and os.sep in value:
            assert value not in said


def test_the_prompt_still_names_no_tools(capsys, monkeypatch):
    """#41's rule, which this row is the first thing to risk breaking.

    A sentence about the shell is one careless word away from naming what the
    shell runs, and the prompt is not allowed to name a tool - the offered set
    varies per run, and a prompt that lists one goes wrong without failing.
    """
    assert "tool" not in tools.machine_and_day().lower()


def test_it_is_one_sentence_worth_of_tokens():
    """Not a criterion - a bound, because everything here rides in every request.

    The whole standing prompt has been measured at ~205 tokens, and the tool
    declarations at ten times that. A machine sentence that grew to a paragraph
    would be paid for on every turn of every session, and #61 exists because
    that cost was invisible until someone printed it.
    """
    weighed = compaction.estimated_tokens(
        [{"role": "system", "content": tools.machine_and_day()}]
    )

    assert weighed < 60, f"the machine sentence costs {weighed} tokens"


def test_it_is_json_safe_for_the_backend():
    """A sentence that cannot be serialised is one no request can carry."""
    assert json.loads(json.dumps(tools.machine_and_day()))

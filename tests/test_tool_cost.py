"""What the declared tools cost, before a word is typed.

The figure existed before this row, inside `note_servers` - a function about
MCP servers, which returns early when none are attached. So a fact about the
*session* was only ever shown to users who happened to configure MCP, and
everyone else was told `7 tools including web` with no idea those seven were
eating 40% of a small window.

Nothing here hard-codes 653 or 807. Those are this machine, today. Every
assertion about the number derives it from `compaction.estimated_tokens` over
the same payload the size checks weigh - which is AC 9, and the reason it
exists is that the standing prompt has been quoted at 56, then 163, then
measured at 205, by three different routes.
"""

import json
import re

import pytest

from axiom import compaction, main, models, tools
from conftest import StubBackend, feed


@pytest.fixture(autouse=True)
def choice(tmp_path, monkeypatch):
    monkeypatch.setattr(
        models, "DEFAULT_CHOICE_FILE", tmp_path / ".axiom" / "model.json"
    )


def run(capsys, monkeypatch, argv=(), typed=(), **stub):
    stub.setdefault("models", ["big:70b"])
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    made = StubBackend(**stub)
    feed(monkeypatch, [*typed, "/exit"])
    main([*argv, "--model", "big:70b"], using=made)
    return made, capsys.readouterr()


def reported(text: str) -> int | None:
    """The cost axiom printed, or None if it said nothing about it."""
    found = re.search(r"tools cost about (\d+) tokens", text)
    return int(found.group(1)) if found else None


def share(text: str) -> str | None:
    """The window share axiom printed, if any."""
    found = re.search(r"tokens per request(?:, (\d+)% of the window)?", text)
    return found.group(1) if found else None


def offered(*, web: bool = True) -> list:
    """What a run in this file actually declares - not the whole registry.

    Since #75 the declared set is smaller than `tools.declarations()`: three of
    the four skill tools are dropped when the catalogue is empty, and every run
    here has an empty one. Reading the figure back from `tools_sent` would be
    better still, but the runs these tests make never take a turn - the cost
    line is printed at startup, before anything is streamed - so there is no
    payload to read.

    Derived from `SKILL_TOOLS` and `WEB_TOOLS` rather than listed, so a tool
    added to either follows automatically.
    """
    dropped = tools.SKILL_TOOLS - {"write_skill"}
    if not web:
        dropped = dropped | tools.WEB_TOOLS
    return [d for d in tools.declarations() if d["function"]["name"] not in dropped]


def weighed(declarations, prompt: str) -> int:
    """The cost as the size checks would weigh it - declarations and prompt."""
    return compaction.estimated_tokens(
        [
            *({"role": "system", "content": json.dumps(d)} for d in declarations),
            {"role": "system", "content": prompt},
        ]
    )


# --- Being told ---------------------------------------------------------


def test_a_run_with_no_server_still_says_what_the_tools_cost(capsys, monkeypatch):
    """AC 1, and the whole reason this row exists.

    Before this, the line lived inside `note_servers`, which returns early
    when nothing is attached - so this run said nothing at all.
    """
    _, out = run(capsys, monkeypatch)

    assert reported(out.out) is not None, "said nothing about what the tools cost"


def test_the_cost_is_given_against_the_window(capsys, monkeypatch):
    """AC 2. A bare number is not a share of what is available."""
    _, out = run(capsys, monkeypatch, infos={"big:70b": {"a.context_length": 2000}})

    assert share(out.out) is not None
    assert "% of the window" in out.out


def test_a_window_that_could_not_be_established_still_gives_the_number(
    capsys, monkeypatch
):
    """AC 2. With no window there is no share to give, and the cost still holds."""
    _, out = run(capsys, monkeypatch, infos={})

    assert reported(out.out) is not None
    assert share(out.out) is None


def test_the_figure_covers_the_standing_prompt_too(capsys, monkeypatch):
    """AC 3. The easy one to forget, and it is a fifth of the answer.

    The prompt is held outside `messages` in the chat loop - deliberately, for
    #42's reasons - so it does not look like part of the conversation. It
    rides in every request all the same.
    """
    _, out = run(capsys, monkeypatch)

    declarations = offered()
    prompt = tools.system_prompt(tools.Limits())
    assert reported(out.out) == weighed(declarations, prompt)

    without = compaction.estimated_tokens(
        [{"role": "system", "content": json.dumps(d)} for d in declarations]
    )
    assert reported(out.out) > without, "the standing prompt was left out"


def test_the_figure_is_the_one_the_size_checks_use(capsys, monkeypatch):
    """AC 9, and it matters more than accuracy.

    `estimated_tokens` divides by four; `too_large` divides by three. A figure
    computed a third way - even a better one - would disagree with the
    behaviour it is describing, and #43's log records this prompt being quoted
    at 56, then 163, before being measured at 205.
    """
    _, out = run(capsys, monkeypatch)

    assert reported(out.out) == weighed(
        offered(), tools.system_prompt(tools.Limits())
    )


def test_the_prompt_measured_is_the_prompt_actually_sent(capsys, monkeypatch):
    """AC 9, and without this the criterion has no test at all.

    Every other test here runs with default settings, and the standing prompt
    names the working directory and the command timeout - so a figure measured
    from a *bare* `Limits()` matches a figure measured from the run's real one,
    and only by coincidence. Breaking `_tool_cost` to use `tools.Limits()`
    left all 520 tests green.

    With non-default settings the two diverge - 807 against 813 - and this is
    the only test that can tell them apart.
    """
    where = "C:/Projects/.tmp/a-much-longer-sandbox-path"
    _, out = run(
        capsys,
        monkeypatch,
        argv=["--working-directory", where, "--command-timeout", "900"],
    )

    real = tools.Limits(working_directory=where, command_timeout=900.0)
    assert reported(out.out) == weighed(offered(), tools.system_prompt(real))
    assert reported(out.out) != weighed(
        offered(), tools.system_prompt(tools.Limits())
    ), "the settings made no difference, so this proves nothing"


def test_it_is_said_once(capsys, monkeypatch):
    """AC 4."""
    _, out = run(capsys, monkeypatch)

    assert out.out.count("tools cost about") == 1


# --- When there is nothing to say ---------------------------------------


def test_tools_switched_off_says_nothing_about_cost(capsys, monkeypatch):
    """AC 5."""
    _, out = run(capsys, monkeypatch, argv=["--no-tools"])

    assert reported(out.out) is None


def test_a_model_that_cannot_call_tools_says_nothing_about_cost(capsys, monkeypatch):
    """AC 6."""
    _, out = run(capsys, monkeypatch, capable={"big:70b": False})

    assert reported(out.out) is None


def test_the_silences_are_not_vacuous(capsys, monkeypatch):
    """AC 5, AC 6 both assert an absence, which passes for an implementation
    that never prints the line at all. This is the positive they lean on."""
    _, out = run(capsys, monkeypatch)

    assert reported(out.out) is not None


# --- Staying true -------------------------------------------------------


def test_switching_the_web_off_lowers_the_figure(capsys, monkeypatch):
    """AC 7, AC 8. Two settings, compared to each other - one number proves
    nothing about what it follows."""
    _, on = run(capsys, monkeypatch)
    _, off = run(capsys, monkeypatch, argv=["--no-web"])

    assert reported(off.out) < reported(on.out)


def test_the_figure_reports_what_is_actually_declared(capsys, monkeypatch):
    """AC 7. With the web off, the cost is of the tools that remain."""
    _, out = run(capsys, monkeypatch, argv=["--no-web"])

    assert reported(out.out) == weighed(
        offered(web=False), tools.system_prompt(tools.Limits())
    )


def test_after_a_switch_the_figure_belongs_to_the_new_model(capsys, monkeypatch):
    """AC 10, the criterion #56's cold read handed over.

    Of everything said at startup, this is the one fact a switch can make
    stale: declarations follow the model, so moving to a model that cannot
    call tools drops the real cost to nothing while a startup figure stands.
    """
    _, out = run(
        capsys,
        monkeypatch,
        typed=["/model small:1b"],
        models=["big:70b", "small:1b"],
        capable={"big:70b": True, "small:1b": False},
    )

    after = out.out[out.out.index("now small:1b") :]
    assert reported(after) is None, "reported a cost for a model with no tools"


def test_a_switch_to_a_capable_model_reports_its_cost(capsys, monkeypatch):
    """AC 10, the other direction - and the positive for the negative above."""
    _, out = run(
        capsys,
        monkeypatch,
        typed=["/model small:1b"],
        models=["big:70b", "small:1b"],
        capable={"big:70b": False, "small:1b": True},
    )

    after = out.out[out.out.index("now small:1b") :]
    assert reported(after) == weighed(
        offered(), tools.system_prompt(tools.Limits())
    )


# --- Unchanged ----------------------------------------------------------


def test_a_server_that_fails_is_still_reported_alongside_the_cost(
    capsys, monkeypatch, tmp_path
):
    """AC 11. This row moves one line out of `note_servers`, not the function.

    A server that cannot start leaves `connected` empty, so the per-server
    count and the bounds line are correctly absent - they are said only when
    something answered. What must survive is the problem, and the cost line
    must now appear even though no server did.
    """
    config = tmp_path / "mcp.json"
    config.write_text(
        json.dumps({"mcpServers": {"probe": {"command": "not-a-program"}}}),
        encoding="utf-8",
    )

    _, out = run(capsys, monkeypatch, argv=["--mcp-file", str(config)])

    assert "probe" in out.err
    assert reported(out.out) is not None


def test_the_server_lines_are_unchanged(capsys):
    """AC 11, AC 12, at the seam.

    `note_servers` keeps the per-server counts, the bounds and the problems -
    and now says nothing about cost. The rest of `tests/test_mcp.py` is the
    wider evidence; this pins the one function this row edited.
    """
    from axiom import terminal

    terminal.note_servers({"tiny": 3}, ["something went wrong"], bounds=(3.0, 9.0))

    out = capsys.readouterr()
    assert "tiny: 3 tools" in out.out
    assert "server start limit 3s, tool call limit 9s" in out.out
    assert "something went wrong" in out.err
    assert "cost" not in out.out

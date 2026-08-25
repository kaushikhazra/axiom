"""#41: what the model is told about its limits and where it is working.

Nothing here needs a model. These are claims about what axiom assembles, where
it puts work, and what it says when a bound is reached. The claims that are
about a model's *behaviour* - AC 1, 3, 4, 5 - are settled by the live probe
recorded in the cycle logs, because a test asserting a prompt contains
"30 seconds" proves a sentence was built and nothing more.
"""

import axiom
from pathlib import Path

from axiom import config, terminal, tools
from axiom.backend import Call
from axiom.tools import Limits
from conftest import StubBackend, feed, history

# --- AC 1 and AC 2: the values told are the ones in force -------------------


def test_the_prompt_states_every_limit_that_applies():
    """AC 1: told before anything runs, rather than discovered by hitting it."""
    prompt = tools.system_prompt(Limits(working_directory="C:/work"))

    assert "30 seconds" in prompt  # the command timeout
    assert "20000 characters" in prompt  # what is kept of a page
    assert "5 results" in prompt  # what a search returns
    assert str(Path("C:/work")) in prompt  # where it is working


def test_changing_a_limit_changes_what_the_model_is_told():
    """AC 2: one value, not a description of one.

    The prompt is built from the same `Limits` the tools are handed, so these
    cannot drift. A second copy of the numbers would pass a spelling check and
    still lie the first time a default moved.
    """
    prompt = tools.system_prompt(
        Limits(
            working_directory="C:/elsewhere",
            command_timeout=5,
            page_characters=99,
            search_results=2,
        )
    )

    assert "5 seconds" in prompt
    assert "99 characters" in prompt
    assert "2 results" in prompt
    assert str(Path("C:/elsewhere")) in prompt
    assert "30 seconds" not in prompt


def test_the_command_line_reaches_what_the_model_is_told(monkeypatch):
    """AC 2, through the real settings rather than a hand-built Limits."""
    monkeypatch.delenv("AXIOM_COMMAND_TIMEOUT", raising=False)
    settings = config.resolve(["--command-timeout", "7", "--search-results", "3"])
    prompt = tools.system_prompt(
        Limits(
            working_directory=settings.working_directory,
            command_timeout=settings.command_timeout,
            search_results=settings.search_results,
            page_characters=settings.page_characters,
        )
    )

    assert "7 seconds" in prompt
    assert "3 results" in prompt


def test_the_environment_reaches_what_the_model_is_told(monkeypatch):
    """AC 2: the environment is a source of settings too."""
    monkeypatch.setenv("AXIOM_COMMAND_TIMEOUT", "11")
    settings = config.resolve([])

    assert "11 seconds" in tools.system_prompt(
        Limits(command_timeout=settings.command_timeout)
    )


def test_the_prompt_names_no_tools_and_no_count():
    """AC 11's neighbour, and #43's problem avoided in advance.

    The tool list already varies with --no-web and #43 makes it vary per run.
    A prompt naming a number would go wrong without anything failing.
    """
    prompt = tools.system_prompt(Limits()).lower()

    assert "tool" not in prompt
    assert "seven" not in prompt
    assert "read_file" not in prompt


def test_the_instructions_are_sent_but_are_not_conversation(monkeypatch, capsys):
    """AC 1: the model has them on every turn, and they are not history.

    Held outside `messages` deliberately - `compaction` treats a leading system
    message as a carried-forward summary.
    """
    backend = StubBackend(turns=[["first"], ["second"]])
    feed(monkeypatch, ["one", "two", "/exit"])

    axiom.main([], using=backend)
    capsys.readouterr()

    for sent in backend.streamed:
        assert sent[0]["role"] == "system"
        assert "limits you are working within" in sent[0]["content"]
    # ...and the conversation itself never holds them.
    assert all(m["role"] != "system" for m in history(backend.streamed[1]))


# --- AC 4, 5 and 6: where work lands ----------------------------------------


def test_a_relative_path_lands_in_the_working_directory(tmp_path):
    """AC 4: work stays where the user expects.

    Before #41, `--working-directory` reached `run_command` as its cwd and
    reached the file tools not at all, so the same relative name meant two
    different places depending on which tool used it.
    """
    limits = Limits(working_directory=str(tmp_path))

    tools.run("write_file", {"path": "notes.txt", "content": "hello"}, limits)

    assert (tmp_path / "notes.txt").read_text(encoding="utf-8") == "hello"


def test_a_path_the_user_named_is_used_exactly(tmp_path):
    """AC 5: honoured wherever it points.

    The instruction must not refuse work the user actually asked for, and an
    absolute path is how they ask for it.
    """
    elsewhere = tmp_path / "somewhere-else"
    elsewhere.mkdir()
    target = elsewhere / "named.txt"
    limits = Limits(working_directory=str(tmp_path / "work"))

    result = tools.run(
        "write_file", {"path": str(target), "content": "as written"}, limits
    )

    assert target.read_text(encoding="utf-8") == "as written"
    assert not result.startswith("error:")


def test_a_path_outside_the_working_directory_is_named(tmp_path):
    """AC 6: visible before the tool runs."""
    outside = tmp_path / "outside" / "f.txt"
    limits = Limits(working_directory=str(tmp_path / "work"))

    assert tools.outside({"path": str(outside)}, limits) == [str(outside.resolve())]


def test_a_path_inside_the_working_directory_is_not_named(tmp_path):
    """AC 6: only the surprising case is called out, or the line is noise."""
    limits = Limits(working_directory=str(tmp_path))

    assert tools.outside({"path": "inside.txt"}, limits) == []
    assert tools.outside({"path": str(tmp_path / "deep" / "inside.txt")}, limits) == []


def test_a_relative_name_that_escapes_is_still_named(tmp_path):
    """AC 6, the case that matters.

    `../secrets.txt` on screen says nothing about where it lands. Resolving is
    the whole point - an echoed argument would have shown the user nothing.
    """
    limits = Limits(working_directory=str(tmp_path / "work"))

    named = tools.outside({"path": "../escaped.txt"}, limits)

    assert named and "escaped.txt" in named[0]
    assert ".." not in named[0], "the path was echoed rather than resolved"


def test_an_outside_path_is_printed_before_the_tool_runs(capsys):
    """AC 6 at the screen, which is where the user actually sees it."""
    terminal.note_tool("write_file", {"path": "f.txt"}, ["C:/elsewhere/f.txt"])

    out = capsys.readouterr().out
    assert "outside the working directory: C:/elsewhere/f.txt" in out


def test_nothing_is_said_when_the_path_is_inside(capsys):
    """AC 12: no extra output for a request that reached no limit."""
    terminal.note_tool("write_file", {"path": "f.txt"}, [])

    assert "outside" not in capsys.readouterr().out


# --- AC 7 and AC 8: when a limit is reached ---------------------------------


def test_a_stopped_command_reads_as_a_rule_not_a_blip():
    """AC 7.

    The old wording - "still running after N seconds - stopped it" - was the
    same shape as "exited with status 3", so a retry looked worth trying.
    """
    result = tools.run(
        "run_command",
        {"command": 'python -c "import time; time.sleep(30)"'},
        Limits(command_timeout=1),
    )

    assert "limit" in result
    assert "every command" in result
    assert "again" in result, "nothing tells the model a retry is pointless"
    assert "1 seconds" not in result, "the plural bug is back"


def test_an_ordinary_failure_is_not_dressed_up_as_a_limit():
    """AC 7's other half: the two must stay distinguishable."""
    result = tools.run("run_command", {"command": 'python -c "raise SystemExit(3)"'})

    assert "status 3" in result
    assert "limit" not in result


def test_a_cut_page_says_there_is_more_and_an_uncut_one_does_not(monkeypatch):
    """AC 8, pinned.

    Already true before #41 - this exists so a later change cannot erode it
    without something failing.
    """
    import httpx

    def served(body: str):
        response = httpx.Response(
            200,
            content=body.encode(),
            headers={"content-type": "text/plain"},
            request=httpx.Request("GET", "https://x.invalid/p"),
        )
        monkeypatch.setattr(tools.httpx, "get", lambda *a, **k: response)  # noqa: ARG005
        return tools.fetch_page("https://x.invalid/p", Limits(page_characters=200))

    cut = served("word " * 5000)
    whole = served("all of it")

    assert "cut here" in cut
    assert "more characters not included" in cut
    assert "cut here" not in whole
    assert whole == "all of it"


# --- AC 9 and AC 10: not retrying into a wall -------------------------------


def failing_call() -> Call:
    return Call("run_command", {"command": 'python -c "raise SystemExit(9)"'})


def test_the_same_command_failing_the_same_way_is_not_run_a_third_time(
    monkeypatch, capsys
):
    """AC 9."""
    backend = StubBackend(
        turns=[[failing_call()], [failing_call()], [failing_call()], ["giving up"]]
    )
    feed(monkeypatch, ["do it", "/exit"])

    axiom.main([], using=backend)
    out = capsys.readouterr().out

    assert "not running it a third time" in out
    assert out.count("status 9") == 2, "it ran a third time, or fewer than twice"


def test_a_command_that_fails_differently_is_still_run(monkeypatch, capsys):
    """AC 9: *the same way* is half the criterion.

    A second, different failure is a new situation and blocking it would refuse
    work that might yet succeed.
    """
    backend = StubBackend(
        turns=[
            [Call("run_command", {"command": 'python -c "raise SystemExit(1)"'})],
            [Call("run_command", {"command": 'python -c "raise SystemExit(2)"'})],
            [Call("run_command", {"command": 'python -c "raise SystemExit(3)"'})],
            ["done"],
        ]
    )
    feed(monkeypatch, ["do it", "/exit"])

    axiom.main([], using=backend)
    out = capsys.readouterr().out

    assert "not running it a third time" not in out
    assert "status 3" in out, "the third attempt was blocked"


def test_a_different_command_failing_the_same_way_is_still_run(monkeypatch, capsys):
    """AC 9: *the same command* is the other half."""
    same_failure = 'python -c "raise SystemExit(4)"'
    backend = StubBackend(
        turns=[
            [Call("run_command", {"command": same_failure})],
            [Call("run_command", {"command": same_failure})],
            [Call("run_command", {"command": f"{same_failure}  "})],
            ["done"],
        ]
    )
    feed(monkeypatch, ["do it", "/exit"])

    axiom.main([], using=backend)

    assert "not running it a third time" not in capsys.readouterr().out


def test_a_failure_whose_output_varies_is_still_the_same_failure(monkeypatch, capsys):
    """AC 9, and the reason it needed fixing.

    Cycle 4 attacked the criterion and broke it. The block compared whole
    result strings, so a command whose output carries a pid, a timestamp or a
    temp path never matched twice and the block never fired - the criterion was
    decorative for a large class of real commands.
    """
    varying = (
        'python -c "import os,sys; sys.stderr.write(str(os.getpid())); '
        'raise SystemExit(9)"'
    )
    call = Call("run_command", {"command": varying})
    backend = StubBackend(turns=[[call], [call], [call], ["giving up"]])
    feed(monkeypatch, ["do it", "/exit"])

    axiom.main([], using=backend)
    out = capsys.readouterr().out

    assert "not running it a third time" in out
    assert out.count("status 9") == 2, "the varying pid defeated the block again"


def test_the_failure_kind_ignores_what_the_command_printed():
    """AC 9 at the seam.

    The failure is the `error:` line. Everything else is the command's own
    output and says nothing about *how* it failed.
    """
    assert tools.failure_kind(
        "stderr:\n24136\nerror: exited with status 9"
    ) == tools.failure_kind("stderr:\n20664\nerror: exited with status 9")

    assert tools.failure_kind("error: exited with status 1") != tools.failure_kind(
        "error: exited with status 2"
    )
    assert tools.failure_kind("all fine, no error at all") == ""


def test_the_block_does_not_carry_between_turns(monkeypatch, capsys):
    """AC 9 is scoped to one turn. A new question starts clean."""
    backend = StubBackend(
        turns=[
            [failing_call()],
            [failing_call()],
            [failing_call()],
            ["giving up"],
            [failing_call()],
            ["and again"],
        ]
    )
    feed(monkeypatch, ["do it", "do it again", "/exit"])

    axiom.main([], using=backend)
    out = capsys.readouterr().out

    assert out.count("status 9") == 3, "the second turn inherited the first's block"


def test_a_turn_that_runs_out_of_rounds_says_so(monkeypatch, capsys):
    """AC 10.

    Before #41 the loop fell out of range(MAX_TOOL_ROUNDS) and the user got
    whatever `reply` held, which after a turn of nothing but tool calls is two
    newlines and no explanation.
    """
    calls = Call("run_command", {"command": "echo still going"})
    backend = StubBackend(turns=[[calls]] * (axiom.MAX_TOOL_ROUNDS + 2))
    feed(monkeypatch, ["do something impossible", "/exit"])

    axiom.main([], using=backend)
    out = capsys.readouterr().out

    assert f"stopped after {axiom.MAX_TOOL_ROUNDS} rounds" in out
    assert "without an answer" in out


def test_a_turn_that_answers_says_nothing_about_rounds(monkeypatch, capsys):
    """AC 12: no extra output when no limit was reached."""
    backend = StubBackend(turns=[["a plain answer"]])
    feed(monkeypatch, ["hello", "/exit"])

    axiom.main([], using=backend)

    assert "rounds" not in capsys.readouterr().out


# --- AC 11: one fixed set of tools ------------------------------------------


def test_the_declarations_do_not_vary_by_model():
    """AC 11."""
    assert tools.declarations() == tools.declarations()
    names = [tool["function"]["name"] for tool in tools.declarations()]
    assert names == list(tools.REGISTRY)


def test_the_limits_are_not_offered_to_the_model_as_arguments():
    """AC 3, structurally.

    `Limits` appears in no schema, and `run()` refuses any argument a tool did
    not declare - so a model asking to change one is refused whatever the
    prompt says. The live probe covers whether it accepts being refused.
    """
    for name in tools.REGISTRY:
        declared = set(tools.REGISTRY[name].parameters.get("properties", {}))
        assert "limits" not in declared
        assert "command_timeout" not in declared

    refused = tools.run("run_command", {"command": "echo hi", "command_timeout": 300})
    assert refused.startswith("error:")
    assert "does not take" in refused

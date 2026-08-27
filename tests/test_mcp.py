"""#43: tools that come from a server axiom did not write.

No test here fetches a server. Where a real session is needed it is
`tests/mcp_server.py` - ours, started with the interpreter running the suite -
per the clause in CLAUDE.md written for this issue.
"""

import json
import sys
from pathlib import Path

import pytest

from axiom import config, servers, terminal, tools
from axiom.config import ServerSpec
from conftest import StubBackend

HERE = Path(__file__).parent


def written(tmp_path: Path, document: dict) -> Path:
    path = tmp_path / ".axiom" / "mcp.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document), encoding="utf-8")
    return path


def ours() -> ServerSpec:
    """Our own server, over stdio, with the interpreter running the suite."""
    return ServerSpec(
        name="tiny",
        command=sys.executable,
        args=(str(HERE / "mcp_server.py"),),
    )


@pytest.fixture
def running():
    started = []

    def start(specs):
        attached = servers.Servers(specs)
        started.append(attached)
        attached.start()
        return attached

    yield start
    for attached in started:
        attached.stop()


# --- AC 1 and AC 2: nothing configured --------------------------------------


def test_no_config_file_means_no_servers(tmp_path, monkeypatch):
    """AC 1."""
    monkeypatch.chdir(tmp_path)
    settings = config.resolve([])

    assert settings.mcp_servers == ()
    assert settings.mcp_problems == ()


def test_a_file_naming_no_servers_is_the_same_as_none(tmp_path):
    """AC 2."""
    path = written(tmp_path, {"mcpServers": {}})

    assert config.read_servers(path) == ((), ())


def test_nothing_is_said_when_nothing_is_configured(capsys):
    """AC 1: a run with no server looks exactly as it did before MCP existed."""
    terminal.note_servers({}, [])

    assert capsys.readouterr() == ("", "")


# --- AC 6: names cannot collide ---------------------------------------------


def test_every_server_tool_carries_its_server(running):
    """AC 6."""
    attached = running((ours(),))

    names = [d["function"]["name"] for d in attached.declarations]
    assert names, "the server contributed nothing"
    assert all(name.startswith("tiny__") for name in names)


def test_a_server_cannot_take_a_built_in_name(running):
    """AC 6, the case it exists for.

    `tests/mcp_server.py` deliberately offers a tool called `read_file`. The
    prefix is what makes the collision impossible rather than unlikely.
    """
    attached = running((ours(),))

    names = {d["function"]["name"] for d in attached.declarations}
    assert "read_file" not in names
    assert "tiny__read_file" in names
    assert set(tools.REGISTRY) & names == set(), "a server reached a built-in name"


def test_a_server_whose_name_contains_the_separator_is_still_callable(running):
    """AC 6, and the bug cycle 4 found by attacking it.

    A server called `a__b` declares `a__b__ping`. Routing used to partition at
    the *first* separator, which reads that as server `a` with tool `b__ping` -
    a server that does not exist. The tools were declared and permanently
    uncallable, and nothing said so.

    Splitting a qualified name cannot be made unambiguous: `a__b__ping` is
    server `a` with tool `b__ping` just as legitimately as server `a__b` with
    tool `ping`. Routing is a lookup built when the tools are declared.
    """
    attached = running((ServerSpec(**{**vars(ours()), "name": "a__b"}),))

    assert attached.owns("a__b__ping"), "the tool was declared but cannot be routed"
    assert attached.run("a__b__ping", {}) == "pong"


def test_a_server_named_after_a_built_in_still_cannot_collide(running):
    """AC 6: `read_file` as a *server* name, not a tool name."""
    attached = running((ServerSpec(**{**vars(ours()), "name": "read_file"}),))

    names = {d["function"]["name"] for d in attached.declarations}
    assert not names & set(tools.REGISTRY)
    assert attached.run("read_file__ping", {}) == "pong"


def test_two_servers_cannot_take_each_others_names():
    """AC 6: and not each other's either. Pure, so no server is needed."""
    assert servers.qualified("a", "ping") != servers.qualified("b", "ping")
    assert servers.split("a__ping") == ("a", "ping")
    assert servers.split("read_file") is None


# --- AC 3, 5, 7, 8: the tools reach the model and work ----------------------


def test_a_named_server_is_running_before_the_first_prompt(running):
    """AC 3."""
    attached = running((ours(),))

    assert attached.connected == {"tiny": 4}
    assert attached.failures == []


def test_the_startup_line_names_each_server_and_its_count(capsys):
    """AC 5."""
    terminal.note_servers({"tiny": 3, "other": 1}, [])

    out = capsys.readouterr().out
    assert "tiny: 3 tools" in out
    assert "other: 1 tool" in out, "the singular is not handled"


def test_a_server_tool_is_declared_like_a_built_in(running):
    """AC 7: same shape, so nothing downstream knows the difference."""
    attached = running((ours(),))

    one = next(
        d for d in attached.declarations if d["function"]["name"] == "tiny__shout"
    )
    assert one["type"] == "function"
    assert set(one["function"]) == {"name", "description", "parameters"}
    assert one["function"]["parameters"]["type"] == "object"
    assert "text" in one["function"]["parameters"]["properties"]


def test_a_server_tool_can_be_called(running):
    """AC 7."""
    attached = running((ours(),))

    assert attached.run("tiny__shout", {"text": "hello"}) == "HELLO"


def test_the_session_stays_open_across_calls(running):
    """AC 8: a tool called later does not restart anything."""
    attached = running((ours(),))

    assert [attached.run("tiny__ping", {}) for _ in range(4)] == ["pong"] * 4


# --- AC 14, 15, 16: secrets -------------------------------------------------


def test_a_reference_is_replaced_from_the_environment(tmp_path, monkeypatch):
    """AC 14: the file holds the name of a secret, never its value."""
    monkeypatch.setenv("A_TOKEN", "s3cret-value")
    path = written(
        tmp_path,
        {"mcpServers": {"s": {"command": "x", "env": {"TOKEN": "${A_TOKEN}"}}}},
    )

    found, problems = config.read_servers(path)

    assert found[0].env == {"TOKEN": "s3cret-value"}
    assert problems == ()
    assert "s3cret-value" not in path.read_text(encoding="utf-8")


def test_an_unset_variable_is_reported_by_name(tmp_path, monkeypatch):
    """AC 15: by name, because that is what tells the user what to set."""
    monkeypatch.delenv("NOT_SET_ANYWHERE", raising=False)
    path = written(
        tmp_path,
        {
            "mcpServers": {
                "s": {"command": "x", "env": {"TOKEN": "${NOT_SET_ANYWHERE}"}}
            }
        },
    )

    found, problems = config.read_servers(path)

    assert any("NOT_SET_ANYWHERE" in p for p in problems)
    assert found[0].env == {"TOKEN": ""}, "the literal reference was passed through"


def test_the_literal_reference_never_reaches_the_server(tmp_path, monkeypatch):
    """AC 15: `${NAME}` as a value would fail far away with nothing useful to say."""
    monkeypatch.delenv("NOT_SET_ANYWHERE", raising=False)
    path = written(
        tmp_path,
        {
            "mcpServers": {
                "s": {"command": "x", "args": ["--token=${NOT_SET_ANYWHERE}"]}
            }
        },
    )

    found, _ = config.read_servers(path)

    assert "${" not in found[0].args[0]


def test_a_failure_never_carries_what_the_server_was_configured_with(running):
    """AC 16.

    A server that will not start often reports its own command line, and that
    command line may hold a value substituted from the environment.
    """
    secret = "s3cret-token-value"
    attached = running(
        (ServerSpec(name="bad", command="no-such-program", args=(secret,)),)
    )

    assert attached.failures, "the broken server did not report a failure"
    assert all(secret not in failure for failure in attached.failures)
    assert all("\n" not in failure for failure in attached.failures)


# --- AC 17 and AC 18: switching it off --------------------------------------


def test_no_mcp_starts_with_no_servers(tmp_path, monkeypatch):
    """AC 17."""
    monkeypatch.chdir(tmp_path)
    written(tmp_path, {"mcpServers": {"s": {"command": "x"}}})

    assert config.resolve([]).mcp_servers != ()
    assert config.resolve(["--no-mcp"]).mcp_servers == ()


def test_the_flag_wins_over_the_environment(tmp_path, monkeypatch):
    """AC 17: the command line beats the environment, as everywhere else."""
    monkeypatch.chdir(tmp_path)
    written(tmp_path, {"mcpServers": {"s": {"command": "x"}}})
    monkeypatch.setenv("AXIOM_MCP", "off")

    assert config.resolve([]).mcp_servers == ()


def test_no_tools_takes_mcp_with_it(tmp_path, monkeypatch):
    """AC 18: the same way it already takes the web."""
    monkeypatch.chdir(tmp_path)
    written(tmp_path, {"mcpServers": {"s": {"command": "x"}}})

    assert config.resolve(["--no-tools"]).mcp_servers == ()


# --- AC 10, 11, 12: choosing what the model is given ------------------------


def test_only_the_named_tools_are_declared(running):
    """AC 10."""
    attached = running((ServerSpec(**{**vars(ours()), "tools": ("ping",)}),))

    names = [d["function"]["name"] for d in attached.declarations]
    assert names == ["tiny__ping"]


def test_naming_no_tools_declares_all_of_them(running):
    """AC 11."""
    attached = running((ours(),))

    assert attached.connected == {"tiny": 4}


def test_a_tool_the_server_does_not_have_is_reported_by_name(running):
    """AC 12: and the other named tools are still declared."""
    attached = running(
        (ServerSpec(**{**vars(ours()), "tools": ("ping", "not_a_real_tool")}),)
    )

    assert any("not_a_real_tool" in f for f in attached.failures)
    assert [d["function"]["name"] for d in attached.declarations] == ["tiny__ping"]


# --- AC 13: what the tools cost ---------------------------------------------


def test_the_cost_of_the_declared_tools_is_shown(capsys):
    """AC 13: before any conversation has started.

    Said by `note_tool_cost` since #61, not by `note_servers`. AC 13 asked
    that the cost be visible, and it was built inside this story - so it
    inherited MCP's scope and was shown only when a server happened to be
    attached. The criterion still holds; the line simply moved to where it
    is always said.
    """
    terminal.note_tool_cost(420, 8192)

    out = capsys.readouterr().out
    assert "420 tokens" in out
    assert "% of the window" in out


# --- AC 19 and AC 20: the bounds are settings, and visible ------------------


def test_the_bounds_have_defaults_and_can_be_changed(tmp_path, monkeypatch):
    """AC 19."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("AXIOM_MCP_START_TIMEOUT", raising=False)
    monkeypatch.delenv("AXIOM_MCP_CALL_TIMEOUT", raising=False)

    assert config.resolve([]).mcp_start_timeout == config.DEFAULT_MCP_START_TIMEOUT
    assert config.resolve([]).mcp_call_timeout == config.DEFAULT_MCP_CALL_TIMEOUT

    changed = config.resolve(["--mcp-start-timeout", "3", "--mcp-call-timeout", "9"])
    assert (changed.mcp_start_timeout, changed.mcp_call_timeout) == (3.0, 9.0)


def test_the_environment_sets_the_bounds_and_the_flag_wins(tmp_path, monkeypatch):
    """AC 19: the command line beats the environment, as everywhere else."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("AXIOM_MCP_START_TIMEOUT", "11")

    assert config.resolve([]).mcp_start_timeout == 11.0
    assert config.resolve(["--mcp-start-timeout", "4"]).mcp_start_timeout == 4.0


def test_the_bounds_in_force_are_visible_at_startup(capsys):
    """AC 20: the half that gets forgotten."""
    terminal.note_servers({"tiny": 1}, [], bounds=(3.0, 9.0))

    out = capsys.readouterr().out
    assert "3s" in out
    assert "9s" in out


def test_the_bound_reaches_the_client(tmp_path, monkeypatch):
    """AC 19: told is not the same as applied."""
    monkeypatch.chdir(tmp_path)
    attached = servers.Servers((), start_timeout=2.0, call_timeout=5.0)

    assert (attached.start_timeout, attached.call_timeout) == (2.0, 5.0)


# --- AC 21, 24, 25: when a server does not work -----------------------------


def test_a_server_that_fails_to_start_does_not_stop_the_others(running):
    """AC 21."""
    attached = running((ServerSpec("bad", "no-such-program"), ours()))

    assert attached.connected == {"tiny": 4}, "the good server was lost with the bad"
    assert any(f.startswith("bad:") for f in attached.failures)
    assert attached.run("tiny__ping", {}) == "pong"


def test_a_server_that_never_speaks_is_given_up_on(running):
    """AC 22, which cycle 3 marked met with no test at all.

    `tests/mcp_hangs.py` starts and then says nothing. Without a bound axiom
    would wait for it before the first prompt, with no way for the user to tell
    a slow start from a hang.
    """
    import time

    hanging = ServerSpec(
        name="hangs", command=sys.executable, args=(str(HERE / "mcp_hangs.py"),)
    )
    started = time.perf_counter()
    attached = servers.Servers((hanging,), start_timeout=3.0)
    attached.start()
    took = time.perf_counter() - started

    assert took < 30, "axiom waited instead of giving up"
    assert attached.connected == {}
    assert any("hangs" in f for f in attached.failures), "gave up without saying so"
    attached.stop()


def test_a_call_that_passes_its_bound_leaves_the_session_usable(running):
    """AC 23: "the model is told so, and the turn carries on".

    #34's lesson applies - a bound that reports a stop while work continues is
    the failure, so this asserts the session still works afterwards rather than
    only that the message is right.
    """
    attached = servers.Servers((ours(),), start_timeout=20.0, call_timeout=0.5)
    attached.start()
    try:
        timed_out = attached.run("tiny__slow", {"seconds": 5})
        assert "did not answer" in timed_out
        assert timed_out.startswith("error:")

        attached.call_timeout = 20.0
        assert attached.run("tiny__ping", {}) == "pong", "the session never recovered"
    finally:
        attached.stop()


def test_a_server_that_dies_fails_only_its_own_tools(running):
    """AC 24 and AC 25.

    Kills the subprocess and checks a built-in still works in the same session -
    the criterion is that *every other tool* keeps working, not that the call
    fails politely.
    """
    import psutil

    attached = running((ours(),))
    assert attached.run("tiny__ping", {}) == "pong"

    me = psutil.Process()
    for child in me.children(recursive=True):
        child.kill()

    result = attached.run("tiny__ping", {})
    assert result.startswith("error:"), "a dead server answered"
    assert "tiny" in result, "the failure does not say which server"
    # Every other tool is untouched.
    assert tools.run("read_file", {"path": str(HERE / "mcp_server.py")}).startswith(
        '"""A tiny MCP server'
    )


# --- AC 26, 27, 28: leaving -------------------------------------------------


def children_of_this_process() -> set[int]:
    import psutil

    return {c.pid for c in psutil.Process().children(recursive=True)}


def surviving(pids: set[int], within: float = 5.0) -> list[int]:
    """Which of these processes are still running, given a moment to stop.

    Waits, deliberately. `Servers.stop()` joins its own thread, but the operating
    system does not necessarily reap the child by the time the next line runs -
    so an instant check is a race, and it loses under load. It cost this suite
    two red tests during #61's cold read, with nothing wrong in the code.

    Waiting removes the race rather than shrinking the window, which is #43's
    own standing note applied to #43's own test. It does not weaken anything: a
    server that genuinely outlives axiom is still alive five seconds later and
    still fails the assertion.
    """
    import time

    import psutil

    deadline = time.monotonic() + within
    while True:
        alive = []
        for pid in pids:
            try:
                process = psutil.Process(pid)
                if process.is_running() and process.status() != psutil.STATUS_ZOMBIE:
                    alive.append(pid)
            except psutil.NoSuchProcess:
                pass
        if not alive or time.monotonic() >= deadline:
            return alive
        time.sleep(0.05)


def configured(tmp_path, monkeypatch) -> None:
    """A real server, ours, named in a real config file."""
    written(
        tmp_path,
        {
            "mcpServers": {
                "tiny": {
                    "command": sys.executable,
                    "args": [str(HERE / "mcp_server.py")],
                }
            }
        },
    )
    monkeypatch.chdir(tmp_path)


class WatchesChildren(StubBackend):
    """Snapshots the server processes *while axiom is running*.

    Sampling after `main()` returns is the trap: `stop()` has already run by
    then, so the set of "spawned" pids is empty and every assertion about
    survivors passes without a server ever having been examined. Cycle 3 wrote
    that test, watched it pass, and checked - the server really had started, 3
    tools and 839 tokens, and the measurement was simply taken too late.
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.seen: set[int] = set()

    def stream(self, model, messages, options=None, tools=None):  # noqa: ANN001
        self.seen |= children_of_this_process()
        return super().stream(model, messages, options, tools)


@pytest.mark.parametrize("leaving", ["/exit", "/quit", EOFError(), KeyboardInterrupt()])
def test_every_route_out_stops_every_server(tmp_path, monkeypatch, capsys, leaving):
    """AC 26: /exit, /quit, end of input, Ctrl-C.

    A real subprocess, because "no server process outlives axiom" cannot be
    shown by an object in the same process. The server is ours, per CLAUDE.md.
    """
    import axiom
    from conftest import feed

    configured(tmp_path, monkeypatch)
    backend = WatchesChildren()
    # One real turn first, so the servers are observed while they are alive.
    feed(monkeypatch, ["hello", leaving])

    axiom.main([], using=backend)
    capsys.readouterr()

    assert backend.seen, "no server was running - the test would prove nothing"
    assert surviving(backend.seen) == [], (
        f"a server outlived axiom leaving by {leaving!r}"
    )


def test_no_server_outlives_a_failure(tmp_path, monkeypatch, capsys):
    """AC 27: including when axiom exits through one.

    Cycle 1 measured that a hard kill leaves no survivors *by inheritance* -
    the server exits when its stdin closes. Proving today's behaviour is not
    the same as owning it, so this asserts the outcome.
    """
    import axiom
    from conftest import feed

    configured(tmp_path, monkeypatch)
    backend = WatchesChildren()
    feed(monkeypatch, ["hello", RuntimeError("something went wrong inside the loop")])

    with pytest.raises(RuntimeError):
        axiom.main([], using=backend)
    capsys.readouterr()

    assert backend.seen, "no server was running - the test would prove nothing"
    assert surviving(backend.seen) == [], "a server outlived an axiom that died"


def test_the_exit_status_is_unaffected(tmp_path, monkeypatch, capsys):
    """AC 28."""
    import axiom
    from conftest import StubBackend, feed

    written(
        tmp_path,
        {
            "mcpServers": {
                "tiny": {
                    "command": sys.executable,
                    "args": [str(HERE / "mcp_server.py")],
                }
            }
        },
    )
    monkeypatch.chdir(tmp_path)
    feed(monkeypatch, ["hello", "/exit"])

    assert axiom.main([], using=StubBackend()) is None
    capsys.readouterr()


# --- AC 9: nothing carries between runs -------------------------------------


def test_each_run_starts_its_own_servers(running):
    """AC 9."""
    first = running((ours(),))
    first_pids = children_of_this_process()
    first.stop()

    second = running((ours(),))
    assert second.run("tiny__ping", {}) == "pong"
    assert surviving(first_pids) == [], "the first run's servers are still going"


# --- AC 4: what is said while waiting ---------------------------------------


def test_the_user_is_told_while_servers_are_starting(capsys):
    """AC 4: a silent pause before the first prompt reads as a hang."""
    terminal.note_starting(2)

    assert "starting 2 MCP servers" in capsys.readouterr().out


def test_nothing_is_said_when_there_are_none(capsys):
    """AC 1 again: a run with no server looks exactly as it did before."""
    terminal.note_starting(0)

    assert capsys.readouterr().out == ""


# --- what the model is told about a result ----------------------------------


class _Block:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


class _Result:
    def __init__(self, content, is_error=False):
        self.content = content
        self.is_error = is_error


def test_text_blocks_are_joined():
    assert (
        servers.as_text(_Result([_Block(text="one"), _Block(text="two")])) == "one\ntwo"
    )


def test_a_block_that_is_not_text_is_named_rather_than_dropped():
    """A model told nothing came back answers from memory - #40's failure."""
    result = servers.as_text(_Result([_Block(type="image", data="...")]))

    assert "image" in result
    assert "cannot be shown as text" in result


def test_an_error_result_gets_the_same_prefix_every_other_failure_has():
    assert servers.as_text(_Result([_Block(text="it broke")], is_error=True)) == (
        "error: it broke"
    )


def test_a_server_that_returns_nothing_says_so():
    assert "nothing" in servers.as_text(_Result([]))

"""#81: a server that is already running somewhere else.

Its own file rather than more of `tests/test_mcp.py`, so `.claude/loop/cited.py`
can read which criteria it claims. #43's tests stay where they are.

**Two pins first, and they come before the feature.** AC 3 is what the whole
issue turns on - a server named by address is *not a subprocess* - and AC 22 is
the promise that a run configuring nothing pays for none of this. Both hold
today, trivially, because no entry can name an address yet. They are written now
so that the cycle which makes one possible cannot land without them going red.
"""

import sys
from pathlib import Path

import pytest

from axiom import config, servers
from axiom.config import ServerSpec
from conftest import StubBackend, feed


HERE = Path(__file__).parent


def ours() -> ServerSpec:
    """Our own server, over stdio, with the interpreter running the suite."""
    return ServerSpec(
        name="tiny",
        command=sys.executable,
        args=(str(HERE / "mcp_server.py"),),
    )


def children() -> set[int]:
    """Processes axiom started, and not their descendants.

    **Direct children, deliberately.** Measured on this machine: one configured
    stdio server produces one direct `python.exe` and *three* processes
    recursively - the server, a `conhost.exe`, and a second `python.exe` the
    launcher spawns. Counting recursively made "one command, one process" read as
    three, and the number would be different again on another platform.

    What AC 3 is about is whether axiom started something. That is the direct
    child.
    """
    import psutil

    return {c.pid for c in psutil.Process().children()}


@pytest.fixture
def running():
    """Servers started by a test, stopped whether it passes or not.

    Row 20 is the only row in this queue that starts processes, and the queue
    runs unattended for hours on 16 GB. Nothing here may outlive its test.
    """
    started = []

    def start(specs):
        attached = servers.Servers(specs)
        started.append(attached)
        attached.start()
        return attached

    yield start
    for attached in started:
        attached.stop()


# --- #81 AC 3: an address is not a subprocess --------------------------------


def test_a_configured_command_spawns_exactly_one_subprocess(running):
    """#81 AC 3, pinned from the side that can be pinned today.

    The criterion is "a server named by address is not started, stopped, or
    waited for as a subprocess", and no entry can name an address yet. What is
    measurable now is the arithmetic the criterion rests on: **one subprocess per
    configured command, and none from anywhere else.** When an address becomes
    configurable, the same count taken with a remote entry added is the whole of
    AC 3 - and it is a count that a `Servers` quietly spawning something for a
    remote entry would fail.

    Counted as a *difference*, because pytest itself may already have children.
    #43's own lifetime tests were written asserting `surviving(spawned) == []`
    where `spawned` was measured after the servers had been stopped - an empty
    set, and an assertion that held for any implementation at all.
    """
    before = children()
    attached = running((ours(),))
    assert attached.run("tiny__ping", {}) == "pong", "the server never answered"
    after = children()

    assert len(after - before) == 1, (
        f"one configured command spawned {len(after - before)} processes"
    )


def test_no_configured_servers_spawn_nothing(running):
    """#81 AC 3's other half, and AC 12's precondition.

    An empty configuration must not reach a transport of any kind. This is what
    goes red if a later cycle gives `Servers.start` something to do before it has
    looked at what it was given.
    """
    before = children()
    running(())
    after = children()

    assert after - before == set(), f"an empty configuration spawned {after - before}"


# --- #81 AC 22, AC 23: a run that configured nothing -------------------------


def test_a_session_with_no_mcp_says_nothing_about_servers(
    capsys, monkeypatch, tmp_path
):
    """#81 AC 22, for this row rather than for the transcript.

    The golden transcript already says this and has not moved in sixteen cycles.
    What a test here adds is a *reason it would move*: it goes red the moment a
    remote code path starts costing a line on a run that configured nothing.

    **`--mcp-file` at a path that does not exist, not `--no-mcp`.** Written with
    the flag first, and that made it AC 23's test wearing AC 22's name: `--no-mcp`
    clears the list before the file is read, so the run configured nothing because
    of the flag rather than because there was nothing to configure. AC 22 is about
    a user who never set any of this up.
    """
    feed(monkeypatch, ["hello", "/exit"])
    config_free = StubBackend(models=["solo:1b"], turns=[["an answer"]])
    from axiom import main

    main(["--mcp-file", str(tmp_path / "nothing-here.json")], using=config_free)
    printed = capsys.readouterr()

    # "http" and "address" were on this list first and both are wrong: the
    # startup line names the Ollama host, which is `http://localhost:11434`.
    # A word list for "said nothing about servers" has to be words that only a
    # server report would use.
    for word in ("mcp", "remote"):
        assert word not in printed.out.lower(), (
            f"a run with no MCP mentioned {word!r}: {printed.out!r}"
        )
        assert word not in printed.err.lower(), (
            f"a run with no MCP mentioned {word!r} on stderr: {printed.err!r}"
        )


def test_no_mcp_switches_off_every_kind_of_server(tmp_path, monkeypatch):
    """#81 AC 23, and it is met by construction rather than by code.

    `config.resolve` returns `mcp_servers: ()` on `--no-mcp` **before the file is
    read at all**, so no entry of any kind survives it and no transport can
    change that. Asserted with a file present and populated, because "no servers
    were configured anyway" is how this passes for the wrong reason.
    """
    path = tmp_path / ".axiom" / "mcp.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        '{"mcpServers": {"tiny": {"command": "echo", "args": ["hi"]}}}',
        encoding="utf-8",
    )

    with_file = config.resolve(["--mcp-file", str(path)])
    assert with_file.mcp_servers, "the sample file configured no servers at all"

    off = config.resolve(["--mcp-file", str(path), "--no-mcp"])
    assert off.mcp_servers == (), f"--no-mcp left {off.mcp_servers}"

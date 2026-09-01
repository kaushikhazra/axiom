"""#81: a server that is already running somewhere else.

Its own file rather than more of `tests/test_mcp.py`, so `.claude/loop/cited.py`
can read which criteria it claims. #43's tests stay where they are.

**Two pins first, and they come before the feature.** AC 3 is what the whole
issue turns on - a server named by address is *not a subprocess* - and AC 22 is
the promise that a run configuring nothing pays for none of this. Both hold
today, trivially, because no entry can name an address yet. They are written now
so that the cycle which makes one possible cannot land without them going red.
"""

import json
import sys
from pathlib import Path

import pytest

from axiom import config, servers, tools
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
    """#81 AC 3's other half.

    AC 12's precondition too, and that number is off the first line deliberately:
    `.claude/loop/cited.py` reads line one as the claim, and this does not test
    what a user is told.

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


# --- #81 AC 1, 2, 4, 5, 16, 17, 18: naming one ------------------------------


def configured(tmp_path: Path, entries: dict):
    """`read_servers` on a file holding `entries`, as the user would write it."""
    path = tmp_path / ".axiom" / "mcp.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"mcpServers": entries}), encoding="utf-8")
    return config.read_servers(path)


def test_a_server_can_be_named_by_address(tmp_path):
    """#81 AC 1. The address survives into the spec exactly as written."""
    servers_read, problems = configured(
        tmp_path, {"far": {"address": "https://tools.example/mcp"}}
    )

    assert problems == (), f"a plain address was refused: {problems}"
    assert len(servers_read) == 1
    assert servers_read[0].address == "https://tools.example/mcp"
    assert servers_read[0].command == "", "an address entry gained a command"


def test_one_file_holds_both_kinds(tmp_path):
    """#81 AC 2's first half - the file.

    That both *work* is AC 6 and AC 7, and neither is claimed here. Their numbers
    are on this line and not the first, because `.claude/loop/cited.py` reads the
    first line as the claim.

    Order matters and is asserted: a reader that dropped one kind while keeping
    the other would still return a non-empty list, and a test that only counted
    would pass.
    """
    servers_read, problems = configured(
        tmp_path,
        {
            "near": {"command": "echo", "args": ["hi"]},
            "far": {"address": "https://tools.example/mcp"},
        },
    )

    assert problems == (), f"a mixed file was refused: {problems}"
    by_name = {spec.name: spec for spec in servers_read}
    assert set(by_name) == {"near", "far"}, f"a mixed file lost one: {by_name}"
    assert by_name["near"].command == "echo" and by_name["near"].address == ""
    assert by_name["far"].address and by_name["far"].command == ""


def test_an_entry_naming_neither_is_refused_and_says_so(tmp_path):
    """#81 AC 4. Refused, and the refusal says what is missing and which entry.

    A project with six servers configured needs to know which one. #55 exists
    because a message named a folder where the user needed a file.
    """
    servers_read, problems = configured(tmp_path, {"empty": {"tools": ["ping"]}})

    assert servers_read == (), "an entry with no way in was configured anyway"
    assert len(problems) == 1, f"expected one refusal, got {problems}"
    assert "empty" in problems[0], f"the refusal does not name the entry: {problems[0]}"
    assert "command" in problems[0] and "address" in problems[0], (
        f"the refusal does not say what is missing: {problems[0]}"
    )


def test_an_entry_naming_both_is_refused_and_says_so(tmp_path):
    """#81 AC 5. Two ways in is not better than one; it is ambiguous.

    Refused rather than resolved by precedence. A rule that quietly preferred one
    would mean a user who added an address to an existing entry, expecting to
    move the server, kept talking to the subprocess and never knew.
    """
    servers_read, problems = configured(
        tmp_path,
        {"both": {"command": "echo", "address": "https://tools.example/mcp"}},
    )

    assert servers_read == (), "an ambiguous entry was configured anyway"
    assert len(problems) == 1, f"expected one refusal, got {problems}"
    assert "both" in problems[0]
    assert "command" in problems[0] and "address" in problems[0], (
        f"the refusal does not say what the conflict is: {problems[0]}"
    )


@pytest.mark.parametrize(
    "address",
    [
        "not a url at all",
        "tools.example/mcp",  # no scheme
        "ftp://tools.example/mcp",  # a scheme, and the wrong one
        "https://",  # a scheme and nothing else
    ],
)
def test_an_address_that_is_not_a_url_is_refused(tmp_path, address):
    """#81 AC 16, and "before anything is attempted" is the half with teeth.

    Refused at configuration time. A rubbish address that reached `Servers`
    would cost a start timeout and report as a connection failure, which sends
    the user looking at the network instead of at the character they mistyped.

    Four shapes, because one would be met by a check that only looked for `://`.
    """
    servers_read, problems = configured(tmp_path, {"bad": {"address": address}})

    assert servers_read == (), f"{address!r} was configured"
    assert problems and "bad" in problems[0], f"unnamed refusal: {problems}"
    assert address in problems[0], (
        f"the refusal does not quote what was written: {problems[0]}"
    )


@pytest.mark.parametrize(
    "address",
    [
        "https://tools.example:8443/mcp",
        "https://tools.example/deep/path/mcp",
        "https://tools.example/mcp?key=value&other=2",
        "https://tools.example:8443/deep/mcp?key=value",
    ],
)
def test_an_address_may_carry_a_port_a_path_and_a_query(tmp_path, address):
    """#81 AC 18, and it is asserted on the address being *unchanged*.

    A validator that accepted a port and quietly dropped the query would satisfy
    AC 16, break this, and never tell the user - which is the shape of every
    truncation this repository has been bitten by.
    """
    servers_read, problems = configured(tmp_path, {"far": {"address": address}})

    assert problems == (), f"{address!r} was refused: {problems}"
    assert servers_read[0].address == address, "the address was rewritten"


def test_a_plain_text_address_says_the_traffic_is_not_encrypted(tmp_path):
    """#81 AC 17, decided as *told* rather than *refused*. See `_unencrypted`.

    The server is still configured - that is what "told rather than refused"
    means, and a test that only checked for the warning would pass for an
    implementation that refused it as well.
    """
    servers_read, problems = configured(
        tmp_path, {"far": {"address": "http://tools.example/mcp"}}
    )

    assert len(servers_read) == 1, "a plain-text address was refused, not reported"
    assert problems and "far" in problems[0], f"nothing was said: {problems}"
    assert "not encrypted" in problems[0], f"the wrong thing was said: {problems[0]}"


def test_localhost_is_told_too(tmp_path):
    """#81 AC 17, and the carve-out that was considered and rejected.

    Staying quiet for `http://localhost` was tempting - it is the ordinary case
    and a line on every run is noise. But loopback traffic is unencrypted, and
    AC 17 says a plain-text address is refused *or* the user is told; silence is
    neither. Reading a criterion loosely to suit the implementation is what #48
    and #49 were both caught by.
    """
    servers_read, problems = configured(
        tmp_path, {"near": {"address": "http://localhost:8080/mcp"}}
    )

    assert len(servers_read) == 1
    assert problems and "not encrypted" in problems[0], (
        f"localhost was quietly exempted: {problems}"
    )


def test_an_https_address_says_nothing(tmp_path):
    """#81 AC 17's other side.

    A warning that fires for everything is not a warning. This is what goes red
    if the check is written as "an address" rather than "a plain-text address".
    """
    _, problems = configured(
        tmp_path, {"far": {"address": "https://tools.example/mcp"}}
    )

    assert problems == (), f"an encrypted address was reported anyway: {problems}"


def test_an_address_entry_is_not_started_as_a_subprocess(running, monkeypatch):
    """#81 AC 3, now that an address entry can exist.

    **Asserted on the transport being opened, not on the process count**, and the
    first version got that wrong. Counting children stayed green against a build
    with the guard removed: `command` is an empty string for an address entry, so
    `stdio_client` tried to run nothing, the exec failed, and no process appeared.
    No child, no tools connected, test green - and axiom had attempted a
    subprocess and waited out its start timeout doing it.

    AC 3 says "not started, stopped, or waited for". An attempt that fails is all
    three. So the spy sits on `stdio_client` itself, where an attempt is visible
    whether or not it succeeds.

    Recorded rather than raised: `_open` catches every `Exception` and turns it
    into a recorded failure, so a raising spy would be swallowed and the test
    would pass for a third wrong reason.
    """
    dialled = []
    monkeypatch.setattr(
        servers, "stdio_client", lambda *args, **kwargs: dialled.append(args)
    )

    before = children()
    attached = running((ServerSpec(name="far", address="https://tools.example/mcp"),))
    after = children()

    assert dialled == [], "a subprocess transport was opened for an address"
    assert after - before == set(), f"an address spawned {after - before}"
    assert attached.connected == {}, "an address entry reported tools"


# --- #81 AC 6, 7, 8: a server that is already answering ----------------------


@pytest.fixture
def listening():
    """Our own server over HTTP, on a port the operating system chose.

    **Never a fixed port.** A hardcoded one fails on a machine where something
    else is listening and, worse, *passes* by talking to whatever that something
    is - a test that silently checks a stranger.

    The server binds the socket itself, prints the port, and hands the bound
    socket to uvicorn, so there is no window in which anything else could take
    it. The alternative - bind to zero, read the number, close, hand the number
    over - is a race that is merely unlikely.

    **Killed in teardown, whatever the test did.** This is the only row in the
    queue that starts processes and the queue runs unattended for hours; an
    orphan per cycle is a machine that stops responding.
    """
    import subprocess

    started = []

    def start(name: str = "far"):
        process = subprocess.Popen(
            [sys.executable, str(HERE / "mcp_server.py"), "--http"],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
        )
        started.append(process)
        line = process.stdout.readline().strip()
        assert line.isdigit(), f"the server did not report a port, it said {line!r}"
        return ServerSpec(name=name, address=f"http://127.0.0.1:{line}/mcp")

    yield start

    for process in started:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:  # pragma: no cover - a wedged server
            process.kill()
            process.wait(timeout=10)


def test_a_remote_server_offers_its_tools_like_any_other(running, listening):
    """#81 AC 6. Same names, same shape, same declarations.

    `declarations` is what the model is handed. A remote server whose tools
    arrived in some other shape would still show up in `connected` and would be
    invisible to a test that only counted.
    """
    attached = running((listening(),))

    assert attached.connected == {"far": 4}, (
        f"the server did not answer: {attached.failures}"
    )
    names = {declared["function"]["name"] for declared in attached.declarations}
    assert names == {"far__ping", "far__shout", "far__read_file", "far__slow"}
    for declared in attached.declarations:
        assert declared["type"] == "function"
        assert declared["function"]["description"], "a remote tool lost its description"


def test_a_remote_tool_is_called_and_answers(running, listening):
    """#81 AC 7. The result comes back as a local one does.

    Two tools, because `ping` takes no arguments and would pass for a call that
    dropped them. `shout` proves an argument arrived and came back changed.
    """
    attached = running((listening(),))

    assert attached.run("far__ping", {}) == "pong"
    assert attached.run("far__shout", {"text": "quietly"}) == "QUIETLY"


def test_both_kinds_work_in_one_session(running, listening):
    """#81 AC 2's second half, and AC 6 with it.

    A file may hold both - proved in cycle 2 - and both must *work*. One
    subprocess and one address in the same `Servers`, both answering, and each
    routed to the right one.
    """
    attached = running((ours(), listening()))

    assert attached.connected == {"tiny": 4, "far": 4}, (
        f"one kind did not answer: {attached.failures}"
    )
    assert attached.run("tiny__ping", {}) == "pong"
    assert attached.run("far__shout", {"text": "both"}) == "BOTH"


def test_two_servers_offering_the_same_tool_stay_apart(running, listening):
    """#81 AC 8. The same tool name on both kinds, told apart by its prefix.

    `read_file` is the name deliberately: it is also a built-in, so this is three
    things called the same thing in one session. #43 chose the `server__tool`
    prefix as both the collision guarantee and the routing key - one mechanism -
    and this is that mechanism meeting a kind of server it did not exist for.
    """
    attached = running((ours(), listening()))

    from_stdio = attached.run("tiny__read_file", {"path": "one"})
    from_remote = attached.run("far__read_file", {"path": "two"})

    # **Asserted on which server answered, not on which path was passed.** Both
    # servers are the same script, so both replies quoted their own argument and
    # differed for that reason alone - and the test stayed green against a build
    # that routed every tool to the first server it had. The script now says how
    # it was started. A test cannot tell two servers apart if the servers cannot.
    assert "stdio server read one" in from_stdio, from_stdio
    assert "http server read two" in from_remote, from_remote
    assert tools.run("read_file", {"path": str(HERE / "mcp_server.py")}).startswith(
        '"""A tiny MCP server'
    ), "the built-in was shadowed"


def test_a_remote_server_whose_name_holds_the_separator(running, listening):
    """#81 AC 8, at the place #43 found it broken.

    #43 cycle 4 found the routing wrong for a server whose *name contained the
    separator*: `odd__name__ping` splits at the first `__` and looks up a server
    called `odd`. The prefix is the collision guarantee and the routing key at
    once, so a name that contains it breaks both halves. A remote name goes
    through exactly the same rule, and this is the test that says so.
    """
    attached = running((listening("odd__name"),))

    assert attached.connected == {"odd__name": 4}, f"{attached.failures}"
    assert attached.run("odd__name__ping", {}) == "pong"

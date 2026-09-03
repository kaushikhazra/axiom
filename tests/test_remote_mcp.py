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

from axiom import config, servers, terminal, tools
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

    def start(name: str = "far", wait: float = 0.0):
        process = subprocess.Popen(
            [sys.executable, str(HERE / "mcp_server.py"), "--http", str(wait)],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
        )
        started.append(process)
        line = process.stdout.readline().strip()
        assert line.isdigit(), f"the server did not report a port, it said {line!r}"
        spec = ServerSpec(name=name, address=f"http://127.0.0.1:{line}/mcp")
        return spec, process

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
    attached = running((listening()[0],))

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
    attached = running((listening()[0],))

    assert attached.run("far__ping", {}) == "pong"
    assert attached.run("far__shout", {"text": "quietly"}) == "QUIETLY"


def test_both_kinds_work_in_one_session(running, listening):
    """#81 AC 2's second half, and AC 6 with it.

    A file may hold both - proved in cycle 2 - and both must *work*. One
    subprocess and one address in the same `Servers`, both answering, and each
    routed to the right one.
    """
    attached = running((ours(), listening()[0]))

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
    attached = running((ours(), listening()[0]))

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
    attached = running((listening("odd__name")[0],))

    assert attached.connected == {"odd__name": 4}, f"{attached.failures}"
    assert attached.run("odd__name__ping", {}) == "pong"


# --- #81 AC 9 to 15, 25: every way it goes wrong -----------------------------


def nothing_listening(name: str = "gone") -> ServerSpec:
    """An address guaranteed to refuse a connection.

    A port bound and immediately released. Nothing can be listening there, which
    makes "cannot be reached" deterministic rather than a guess about the
    network - and it needs no server, so nothing has to be cleaned up.

    The reverse of the `listening` fixture's rule and for the same reason: a port
    picked out of the air might have someone on it, and the test would then be
    checking a stranger.
    """
    import socket

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as free:
        free.bind(("127.0.0.1", 0))
        port = free.getsockname()[1]
    return ServerSpec(name=name, address=f"http://127.0.0.1:{port}/mcp")


def test_the_user_is_told_which_remote_servers_answered(capsys, running, listening):
    """#81 AC 9. The same line a stdio server gets, and that is the point.

    `note_servers` already draws "name: N tools" and knows nothing about
    transports. What is asserted is that a remote server reaches it identically -
    if a remote count needed a line of its own, AC 6's "indistinguishable in use"
    would be false at the only place the user actually looks.

    **The count comes from a server that really answered.** Written first as
    `note_servers({spec.name: 4}, [])` with the four typed in by hand, which
    tested `note_servers` and nothing else - a `_open` that counted a remote
    server's tools wrongly, or not at all, would have sailed through it.
    """
    spec, _ = listening()
    attached = running((spec,))
    terminal.note_servers(attached.connected, attached.failures)
    said = capsys.readouterr()

    assert "far: 4 tools" in said.out, f"the count was not reported: {said.out!r}"


def test_a_server_that_cannot_be_reached_is_named_with_a_reason(running):
    """#81 AC 10. Named, with the reason, and the session carries on.

    Three claims and all three are asserted. A failure that named the server and
    not the reason would send the user to a working config file; one that gave
    the reason without the name is useless with six servers configured.
    """
    attached = running((nothing_listening(),))

    assert attached.connected == {}, "an unreachable server reported tools"
    assert len(attached.failures) == 1, f"expected one failure: {attached.failures}"
    assert attached.failures[0].startswith("gone:"), attached.failures[0]
    assert attached.failures[0] != "gone:", "named, but with no reason given"
    assert attached.started, "the session did not carry on"


def test_a_run_that_reaches_none_of_its_servers_still_works(capsys, monkeypatch):
    """#81 AC 25. Driven through `main`, because "usable" is about the session.

    A `Servers` that reports failures and a session that still answers are two
    different claims, and only the second is what a user cares about. This asks
    for a turn after the failure and reads the answer.
    """
    from axiom import main

    monkeypatch.setattr(
        config,
        "read_servers",
        lambda path: ((nothing_listening(),), ()),
    )
    feed(monkeypatch, ["hello", "/exit"])
    stub = StubBackend(models=["solo:1b"], turns=[["an answer anyway"]])

    main([], using=stub)
    shown = capsys.readouterr()

    assert "an answer anyway" in shown.out, "the session was not usable"
    assert "gone" in shown.err, f"the unreachable server was not named: {shown.err!r}"


def test_a_slow_server_does_not_hold_the_session_past_the_start_limit(listening):
    """#81 AC 11, and the race is removed rather than shrunk.

    **Slow to accept, not slow to answer.** The server binds and listens, so the
    connection completes, and then sleeps thirty seconds before uvicorn reads
    anything. A tool that merely slept before replying would race the bound - and
    #43's cycle 4 watched exactly that coin toss, a 1 ms timeout against a server
    answering in about a millisecond.

    Asserted on the clock as well as the outcome: a start bound that was ignored
    would still fail eventually, and "it failed" is not the criterion.
    """
    import time

    spec, _ = listening(wait=30.0)
    attached = servers.Servers((spec,), start_timeout=1.0)
    began = time.monotonic()
    try:
        attached.start()
        took = time.monotonic() - began

        assert attached.connected == {}, "a server that never answered reported tools"
        # Against the bound, not against the server's thirty seconds. `< 15`
        # was the first threshold and it is halfway to meaningless: the two
        # guards give up after about one second each, so anything under five is
        # the bound working and anything over is it not.
        assert took < 5.0, f"the start bound did not hold: {took:.1f}s"
    finally:
        attached.stop()


def test_a_call_past_the_call_limit_is_abandoned_and_says_so(listening):
    """#81 AC 15. The `slow` tool exists for this and #43 uses it the same way.

    A real wait rather than a tiny bound, for the reason above. And the session
    has to survive it, or "abandoned" would mean "ended".
    """
    spec, _ = listening()
    attached = servers.Servers((spec,), call_timeout=1.0)
    try:
        attached.start()
        answer = attached.run("far__slow", {"seconds": 30})

        assert answer.startswith("error:"), f"a call past its bound returned {answer!r}"
        assert "far__slow" in answer or "far" in answer, (
            f"the failure does not say which tool: {answer!r}"
        )
    finally:
        attached.stop()


def test_a_server_that_stops_answering_is_reported_when_called(running, listening):
    """#81 AC 13 and AC 14 together, and AC 14 is the half that matters.

    The server is killed between two calls. What is asserted is not only that the
    dead one fails politely, but that **everything else still works** - another
    server's tool and a built-in, in the same session, after the failure. A turn
    that ended would satisfy "was reported" and fail the user.
    """
    spec, process = listening()
    attached = running((ours(), spec))
    assert attached.run("far__ping", {}) == "pong", "the server never answered"

    process.terminate()
    process.wait(timeout=10)

    answer = attached.run("far__ping", {})
    assert answer.startswith("error:"), f"a dead server answered {answer!r}"
    assert "far" in answer, f"the failure does not say which server: {answer!r}"

    assert attached.run("tiny__ping", {}) == "pong", "the other server went with it"
    assert tools.run("read_file", {"path": str(HERE / "mcp_server.py")}).startswith(
        '"""A tiny MCP server'
    ), "a built-in went with it"


def test_a_run_with_no_remote_servers_says_nothing_about_them(capsys, running):
    """#81 AC 12. Configured servers, none of them remote, and no remote word.

    Not AC 22's test with a different name: that run configured nothing at all.
    This one has a server, gets a line about it, and the line must carry no
    vocabulary that only exists because remote servers do.
    """
    attached = running((ours(),))
    terminal.note_servers(attached.connected, attached.failures)
    said = capsys.readouterr()

    assert "tiny: 4 tools" in said.out, (
        f"the stdio server was not reported: {said.out!r}"
    )
    for word in ("remote", "address", "http", "url"):
        assert word not in said.out.lower(), f"a stdio-only run said {word!r}"


# --- #81 AC 19, 20: what is left behind --------------------------------------


def test_nothing_about_a_remote_server_is_written_to_disk(running, listening, tmp_path):
    """#81 AC 19. Scoped to the working directory, which is where axiom writes.

    A claim about absence needs a place to be absent from. The remembered-model
    file and the skills directory are both already redirected into `tmp_path` by
    `conftest`, so anything axiom wrote about a server would land there.
    """
    import os

    was = os.getcwd()
    os.chdir(tmp_path)
    try:
        before = set(tmp_path.rglob("*"))
        spec, _ = listening()
        attached = running((spec,))
        assert attached.run("far__ping", {}) == "pong"
        after = set(tmp_path.rglob("*"))
    finally:
        os.chdir(was)

    assert after == before, f"a remote server left {after - before} on disk"


def test_leaving_closes_the_connection(running, listening):
    """#81 AC 20, measured rather than argued.

    `terminate_on_close=True` sends a DELETE when the context exits, which is the
    mechanism - but reading the SDK's source and believing it is not a test.

    **Counted on axiom's own side, not the server's.** Written first against the
    server process, and it reported no connections at all at any point - psutil
    cannot enumerate that process's sockets here, so the test would have "passed"
    by measuring nothing. Measured instead: axiom holds one established connection
    to that port while the session is open and none after `stop()`. That is also
    the side axiom is responsible for.

    The first assertion is the guard against measuring nothing twice: with no
    connection to begin with, the second proves nothing.

    **Polled for two seconds, not ten**, and the number is load-bearing. httpx
    expires an idle keep-alive connection after five, so a ten-second poll waits
    out the keep-alive and reports success whether or not axiom closed anything -
    which is why the first two breaks against this stayed green. Two seconds is
    inside that window: the connection is still alive unless something closed it.

    Polled at all rather than checked once because a socket closing is not
    instantaneous, and a single check would be #43 cycle 4's race pointing the
    other way.
    """
    import time

    import psutil

    spec, _ = listening()
    port = int(spec.address.rsplit(":", 1)[1].split("/")[0])
    me = psutil.Process()

    def held() -> list:
        return [
            c
            for c in me.net_connections()
            if c.raddr and c.raddr.port == port and c.status == "ESTABLISHED"
        ]

    attached = servers.Servers((spec,))
    attached.start()
    try:
        assert attached.run("far__ping", {}) == "pong"
        assert held(), "nothing was connected to begin with, so nothing was proved"
    finally:
        attached.stop()

    deadline = time.monotonic() + 2.0
    while held() and time.monotonic() < deadline:
        time.sleep(0.1)

    assert not held(), f"leaving left {len(held())} connection(s) open"


# --- #81 AC 21, AC 24: nothing else moved ------------------------------------


def test_a_command_server_behaves_as_it_did(running, listening):
    """#81 AC 21. A stdio server is untouched by a remote one being there.

    **The real evidence for this criterion is #43's forty-five tests**, which
    pass untouched across every cycle of this row and went red twenty at a time
    when cycle 3 lost three imports. That is a break watched going red, and it is
    a stronger statement than any single test written here could make.

    What this adds is the case #43 cannot have: the same stdio server with a
    remote one alongside it. Same tool count, same names, same answers.
    """
    alone = running((ours(),))
    counts_alone = dict(alone.connected)
    answer_alone = alone.run("tiny__shout", {"text": "same"})

    together = running((ours(), listening()[0]))

    assert together.connected["tiny"] == counts_alone["tiny"], (
        "a remote server changed how many tools the stdio one declared"
    )
    assert together.run("tiny__shout", {"text": "same"}) == answer_alone
    assert answer_alone == "SAME"


def test_a_redirected_run_is_unchanged_by_a_remote_server(capsys, monkeypatch):
    """#81 AC 24. Not a terminal, so the plain path, remote server or not.

    A configured remote server must not make a redirected run start emitting
    escape sequences or a different startup line - that is what the golden
    transcript is 477 lines of, and it has not moved in sixteen cycles.
    """
    from axiom import main

    monkeypatch.setattr(
        config, "read_servers", lambda path: ((nothing_listening(),), ())
    )
    feed(monkeypatch, ["hello", "/exit"])
    stub = StubBackend(models=["solo:1b"], turns=[["an answer"]])

    main([], using=stub)
    shown = capsys.readouterr()

    assert shown.out.startswith("axiom: "), (
        f"the run no longer opens plainly: {shown.out[:60]!r}"
    )
    assert "\x1b" not in shown.out, "escape sequences reached a redirected run"

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


def test_two_servers_cannot_take_each_others_names():
    """AC 6: and not each other's either. Pure, so no server is needed."""
    assert servers.qualified("a", "ping") != servers.qualified("b", "ping")
    assert servers.split("a__ping") == ("a", "ping")
    assert servers.split("read_file") is None


# --- AC 3, 5, 7, 8: the tools reach the model and work ----------------------


def test_a_named_server_is_running_before_the_first_prompt(running):
    """AC 3."""
    attached = running((ours(),))

    assert attached.connected == {"tiny": 3}
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

"""Config files are read however the user's editor or shell saved them.

Every test here writes **bytes**, not strings. That is the whole point: the
criterion is about a file some other program left behind, and a Python string
with `\\ufeff` prepended is not that. The suite already had 453 tests over these
two files and none of them could fail, because every one wrote its config with
`Path.write_text(encoding="utf-8")` - Python's own encoding, which never emits a
byte order mark. PowerShell's `Set-Content -Encoding utf8` always does.

That is the same fault as `given_page` announcing `text/plain` over HTML in #40:
a stub that contradicts the thing under test.
"""

import json
from pathlib import Path

import pytest

from axiom import config, models


BOM = b"\xef\xbb\xbf"

SERVERS = {
    "mcpServers": {
        "tiny": {
            "command": "C:/Projects/axiom/.venv/Scripts/python.exe",
            "args": ["C:/Projects/axiom/tests/mcp_server.py", "--flag"],
        }
    }
}

# Kept separate. A `${NAME}` reference that is not set is reported as a problem
# - correctly - so folding one into the shared fixture would make every test
# here assert against a problem list that is never empty, for a reason that has
# nothing to do with encoding.
SERVERS_WITH_ENV = {
    "mcpServers": {
        "tiny": {
            "command": "python",
            "env": {"TOKEN": "${MADE_UP_TOKEN}"},
        }
    }
}


def written(path: Path, document: dict, mark: bool) -> Path:
    """A config file as another program would leave it on disk."""
    raw = json.dumps(document, indent=2).encode("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(BOM + raw if mark else raw)
    return path


# --- Reading ------------------------------------------------------------


def test_an_mcp_config_with_a_mark_is_read(tmp_path):
    """AC 1, AC 3. The file that started this - written the way Windows writes one."""
    servers, problems = config.read_servers(
        written(tmp_path / "mcp.json", SERVERS, True)
    )

    assert problems == ()
    assert len(servers) == 1


def test_a_marked_file_behaves_exactly_as_an_unmarked_one(tmp_path):
    """AC 1. Same content, same result - the mark changes nothing at all."""
    with_mark = config.read_servers(written(tmp_path / "a.json", SERVERS, True))
    without = config.read_servers(written(tmp_path / "b.json", SERVERS, False))

    assert with_mark == without


def test_an_unmarked_file_still_reads(tmp_path):
    """AC 2. The permissive decoder must not break the ordinary case."""
    servers, problems = config.read_servers(
        written(tmp_path / "mcp.json", SERVERS, False)
    )

    assert problems == ()
    assert len(servers) == 1


def test_a_remembered_choice_with_a_mark_is_read(tmp_path):
    """AC 3. Both config files, not just the one that was reported."""
    where = written(tmp_path / "model.json", {"http://h:1": "ornith:9b"}, True)

    assert models.read_choice("http://h:1", where) == "ornith:9b"


def test_a_marked_choice_file_is_not_called_broken(tmp_path):
    """AC 3. `unreadable` decides whether the user is told the file is bad."""
    where = written(tmp_path / "model.json", {"http://h:1": "ornith:9b"}, True)

    assert models.unreadable(where) is False


# --- The mark never becomes a value -------------------------------------


def test_no_value_carries_the_mark(tmp_path):
    """AC 4, and the one a careless fix breaks.

    Stripping the mark at the top level and decoding the rest as `utf-8`
    leaves `\\ufeff` glued to the first key or the first value - so a server is
    named `\\ufefftiny`, its command cannot be run, and every test that merely
    counts servers still passes because one was parsed.
    """
    servers, _ = config.read_servers(written(tmp_path / "mcp.json", SERVERS, True))
    server = servers[0]

    assert server.name == "tiny"
    assert server.command == "C:/Projects/axiom/.venv/Scripts/python.exe"
    assert server.args == ("C:/Projects/axiom/tests/mcp_server.py", "--flag")
    assert "\ufeff" not in "".join([server.name, server.command, *server.args])


def test_no_environment_variable_name_carries_the_mark(tmp_path, monkeypatch):
    """AC 4. A `${NAME}` reference is resolved by name - a mark on it fails silently."""
    monkeypatch.setenv("MADE_UP_TOKEN", "not-a-real-secret")
    servers, problems = config.read_servers(
        written(tmp_path / "mcp.json", SERVERS_WITH_ENV, True)
    )

    assert problems == (), "the variable was looked up under a marked name"
    assert servers[0].env == {"TOKEN": "not-a-real-secret"}


def test_no_host_key_carries_the_mark(tmp_path):
    """AC 4. The remembered choice is keyed by host - a marked key never matches."""
    where = written(tmp_path / "model.json", {"http://h:1": "ornith:9b"}, True)

    assert models.read_choice("http://h:1", where) == "ornith:9b"
    assert models.read_choice("\ufeffhttp://h:1", where) is None


# --- Writing ------------------------------------------------------------


def test_axiom_writes_no_mark(tmp_path):
    """AC 5."""
    where = tmp_path / ".axiom" / "model.json"

    assert models.write_choice("ornith:9b", "http://h:1", where) is None
    assert not where.read_bytes().startswith(BOM)


def test_rewriting_a_marked_file_removes_the_mark(tmp_path):
    """AC 5, AC 6. It does not gain a second one, and it does not keep the first."""
    where = written(tmp_path / "model.json", {"http://h:1": "a:1b"}, True)

    assert models.write_choice("b:2b", "http://h:2", where) is None

    raw = where.read_bytes()
    assert not raw.startswith(BOM)
    assert BOM not in raw
    assert json.loads(raw.decode("utf-8")) == {
        "http://h:1": "a:1b",
        "http://h:2": "b:2b",
    }


# --- Still failing when it should ---------------------------------------


def test_rubbish_is_still_reported_in_todays_words(tmp_path):
    """AC 7. A permissive decoder must not start accepting what it should refuse."""
    where = tmp_path / "mcp.json"
    where.write_bytes(BOM + b"{ not json at all")

    servers, problems = config.read_servers(where)

    assert servers == ()
    assert len(problems) == 1
    assert str(where) in problems[0]
    assert "could not be read" in problems[0]


def test_a_document_that_is_not_an_object_is_still_reported(tmp_path):
    """AC 8."""
    where = tmp_path / "mcp.json"
    where.write_bytes(BOM + b'["not", "an", "object"]')

    servers, problems = config.read_servers(where)

    assert servers == ()
    assert problems == (f"{where} has no mcpServers section",)


def test_a_file_with_no_servers_section_is_still_reported(tmp_path):
    """AC 8."""
    where = written(tmp_path / "mcp.json", {"something": "else"}, True)

    servers, problems = config.read_servers(where)

    assert servers == ()
    assert problems == (f"{where} has no mcpServers section",)


def test_a_broken_choice_file_is_still_called_broken(tmp_path):
    """AC 7. The mark must not make a bad file look fine."""
    where = tmp_path / "model.json"
    where.write_bytes(BOM + b"]] broken [[")

    assert models.unreadable(where) is True
    assert models.read_choice("http://h:1", where) is None


def test_a_missing_file_is_not_called_broken(tmp_path):
    """AC 7. Absent and malformed are different, and stay different."""
    assert models.unreadable(tmp_path / "nothing.json") is False


# --- Everywhere ---------------------------------------------------------


def test_nothing_about_the_decoding_branches_on_the_platform():
    """AC 9, and it cannot be tested by running - only by reading.

    A mark is a mark wherever it was written, and a config file written on
    Windows may be read on Linux. A test cannot see a branch that only fires
    on the platform it is not running on, so this asserts the branch is absent.
    """
    source = Path(config.__file__).parent
    for module in ("config.py", "models.py"):
        text = (source / module).read_text(encoding="utf-8")
        for marker in ("sys.platform", "os.name", "platform.system"):
            assert marker not in text, f"{module} decides something by platform"


@pytest.mark.parametrize("module", ["config.py", "models.py"])
def test_every_config_read_is_permissive(module):
    """AC 3. Four reads decode config as JSON, and a fix that missed one would
    leave a file readable in one place and broken in another."""
    source = (Path(config.__file__).parent / module).read_text(encoding="utf-8")

    assert 'read_text(encoding="utf-8")' not in source, "a strict read remains"
    assert 'read_text(encoding="utf-8-sig")' in source

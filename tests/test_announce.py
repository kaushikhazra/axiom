"""Being told the first time axiom writes a file into a directory of yours.

Most of these criteria are about something *not* being said, which is the
easiest assertion in the world to satisfy by accident - an implementation that
never announces anything passes every one of them. So every negative here sits
beside a positive proving the announcement works at all, the way #48 AC 14's
four negatives are built.

The case that separates right from wrong is a directory that **already has**
`.axiom/mcp.json` and no `model.json`. An empty directory does not test this
row: the behaviour before #55 announces there correctly, which is exactly why
the hole survived a cold read.
"""

import json

import pytest

from axiom import main, models
from conftest import StubBackend, feed


HOST = "http://localhost:11434"
INSTALLED = ["gemma2:2b", "gemma4:e2b", "ornith:9b"]


@pytest.fixture
def axiom_dir(tmp_path, monkeypatch):
    """The `.axiom/` folder, with the choice file pointed inside it."""
    where = tmp_path / ".axiom"
    monkeypatch.setattr(models, "DEFAULT_CHOICE_FILE", where / "model.json")
    return where


def with_mcp_config(folder):
    """A project that configures MCP - so `.axiom/` exists and holds no choice."""
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "mcp.json").write_text(json.dumps({"mcpServers": {}}), encoding="utf-8")
    return folder


def run(capsys, monkeypatch, typed, argv=None, **stub):
    stub.setdefault("models", INSTALLED)
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    made = StubBackend(**stub)
    feed(monkeypatch, [*typed, "/exit"])
    main(argv or [], using=made)
    return made, capsys.readouterr()


# --- Being told ---------------------------------------------------------


def test_a_project_that_already_has_the_folder_is_still_told(
    capsys, monkeypatch, axiom_dir
):
    """AC 1, AC 3, and the whole reason this row exists.

    Every project that configures MCP already has `.axiom/mcp.json`. Under
    #48 AC 30 - which asks about the *folder* - axiom creates nothing here, so
    it says nothing, and writes `model.json` in there silently on this run and
    every run after.
    """
    with_mcp_config(axiom_dir)

    _, out = run(capsys, monkeypatch, ["2"])

    assert "remembering this choice in" in out.out
    assert (axiom_dir / "model.json").is_file()


def test_a_directory_with_nothing_in_it_is_told_too(capsys, monkeypatch, axiom_dir):
    """AC 4. The case that already worked must keep working."""
    _, out = run(capsys, monkeypatch, ["2"])

    assert "remembering this choice in" in out.out


def test_the_path_named_is_the_file(capsys, monkeypatch, axiom_dir):
    """AC 2. A user told about a folder is left to guess which file."""
    with_mcp_config(axiom_dir)

    _, out = run(capsys, monkeypatch, ["2"])

    said = next(line for line in out.out.splitlines() if "remembering" in line)
    assert "model.json" in said
    assert "mcp.json" not in said


# --- Not being told twice -----------------------------------------------


def test_the_second_run_says_nothing(capsys, monkeypatch, axiom_dir):
    """AC 5. Two separate runs - a single run cannot see a repeat."""
    _, first = run(capsys, monkeypatch, ["2"])
    assert "remembering this choice in" in first.out

    _, second = run(capsys, monkeypatch, ["3"])
    assert "remembering this choice in" not in second.out


def test_choosing_the_same_model_again_says_nothing(capsys, monkeypatch, axiom_dir):
    """AC 6."""
    run(capsys, monkeypatch, ["2"])

    _, again = run(capsys, monkeypatch, ["2"])

    assert "remembering this choice in" not in again.out


def test_the_file_decides_and_nothing_is_remembered_between_runs(
    capsys, monkeypatch, axiom_dir
):
    """AC 7, and the criterion a flag-based implementation fails.

    A variable saying "already announced" is true within a run and forgotten
    between them. The file's existence is what decides - so deleting it makes
    axiom announce again, and no amount of remembering could produce that.
    """
    run(capsys, monkeypatch, ["2"])
    _, silent = run(capsys, monkeypatch, ["2"])
    assert "remembering this choice in" not in silent.out

    (axiom_dir / "model.json").unlink()

    _, again = run(capsys, monkeypatch, ["2"])
    assert "remembering this choice in" in again.out


def test_an_empty_file_counts_as_the_file_being_there(capsys, monkeypatch, axiom_dir):
    """AC 7 against AC 1, on a state the two criteria read differently.

    An empty `model.json` holds no remembered choice - `read_choice` returns
    None and `unreadable` returns True - so AC 1 ("the first time axiom writes
    its remembered choice") argues for announcing. AC 7 says the announcement
    is decided by "the file being there", and it is there.

    **AC 7 wins, deliberately.** The alternative announces on every run for as
    long as the file stays unusable, which is noise on top of a problem rather
    than help. And the user is not left unaware: an unusable file already
    produces its own line, from #48 AC 33 - it names the path and says axiom is
    carrying on as though nothing had been chosen. They are told about the
    file, just not by this line.
    """
    axiom_dir.mkdir(parents=True)
    (axiom_dir / "model.json").write_text("", encoding="utf-8")

    _, out = run(capsys, monkeypatch, ["2"])

    assert "remembering this choice in" not in out.out
    # But not silent about it, which is what makes the trade acceptable.
    assert "could not be read" in out.err
    assert json.loads((axiom_dir / "model.json").read_text(encoding="utf-8"))


def test_a_directory_where_the_file_should_be_fails_without_claiming_a_write(
    capsys, monkeypatch, axiom_dir
):
    """AC 11, on the strangest state a path can be in.

    `exists()` is true for a directory, so nothing is announced - and the write
    then fails. The criterion that matters is that the failure is reported and
    no file is claimed.
    """
    (axiom_dir / "model.json").mkdir(parents=True)

    _, out = run(capsys, monkeypatch, ["2"])

    assert "could not remember this choice" in out.err
    assert "remembering this choice in" not in out.out


# --- Where it can happen ------------------------------------------------


def test_a_pick_from_the_startup_list_announces(capsys, monkeypatch, axiom_dir):
    """AC 8."""
    with_mcp_config(axiom_dir)

    _, out = run(capsys, monkeypatch, ["2"])

    assert "remembering this choice in" in out.out


def test_a_mid_session_switch_announces_in_the_same_words(
    capsys, monkeypatch, axiom_dir
):
    """AC 9. Both routes call `_remember`, and both must say it identically."""
    with_mcp_config(axiom_dir)

    def announcement(text):
        """The announcement itself, without whatever prompt shares its line.

        The prompt is printed without a newline, so the captured line carries
        `> ` before a switch and the model question before a startup pick.
        That is the harness, not a difference in what axiom said.
        """
        said = [line for line in text.splitlines() if "remembering" in line]
        assert len(said) == 1
        return said[0][said[0].index("axiom: remembering") :]

    _, switched = run(
        capsys, monkeypatch, ["/model ornith:9b"], argv=["--model", "gemma2:2b"]
    )

    (axiom_dir / "model.json").unlink()
    _, picked = run(capsys, monkeypatch, ["2"])

    assert announcement(switched.out) == announcement(picked.out), (
        "the two routes do not say it the same way"
    )


# --- Not being told about nothing ---------------------------------------


@pytest.mark.parametrize(
    ("argv", "env", "typed", "stub"),
    [
        (["--model", "ornith:9b"], None, [], {}),
        (None, "ornith:9b", [], {}),
        (None, None, [], {"models": ["solo:1b"]}),
    ],
    ids=["a flag", "an environment variable", "the single model"],
)
def test_a_run_that_writes_nothing_announces_nothing(
    capsys, monkeypatch, axiom_dir, argv, env, typed, stub
):
    """AC 10, three of the four routes that settle without writing."""
    if env:
        monkeypatch.setenv("AXIOM_MODEL", env)

    _, out = run(capsys, monkeypatch, typed, argv=argv, **stub)

    assert "remembering this choice in" not in out.out
    assert not (axiom_dir / "model.json").exists()


def test_a_run_with_no_terminal_announces_nothing(capsys, monkeypatch, axiom_dir):
    """AC 10, the fourth route."""
    monkeypatch.setattr("sys.stdin.isatty", lambda: False)
    feed(monkeypatch, ["/exit"])
    main([], using=StubBackend(models=INSTALLED))

    out = capsys.readouterr()
    assert "remembering this choice in" not in out.out
    assert not (axiom_dir / "model.json").exists()


def test_the_negatives_are_not_vacuous(capsys, monkeypatch, axiom_dir):
    """AC 10's four negatives all assert an absence.

    Every one of them passes for an implementation that never announces
    anything at all, so this is the positive they lean on: the same fixture,
    the same directory, a route that *does* write - and it speaks.
    """
    _, out = run(capsys, monkeypatch, ["2"])

    assert "remembering this choice in" in out.out
    assert (axiom_dir / "model.json").exists()


# --- A save that fails --------------------------------------------------


def test_a_failed_save_says_so_and_claims_no_file(capsys, monkeypatch, axiom_dir):
    """AC 11, with the directory failing. Two assertions, and the second is the
    one a careless fix drops."""

    def refuse(*args, **kwargs):
        raise OSError("read-only file system")

    monkeypatch.setattr(models.Path, "mkdir", refuse)

    _, out = run(capsys, monkeypatch, ["2"])

    assert "could not remember this choice" in out.err
    assert "remembering this choice in" not in out.out, "claimed a file it never wrote"
    assert not (axiom_dir / "model.json").exists()


def test_a_failed_write_says_so_too(capsys, monkeypatch, axiom_dir):
    """AC 11, with the *write* failing rather than the directory.

    A different failure with a different shape: the folder is created, so
    `.axiom/` now exists while `model.json` does not. An implementation that
    decided what to say from the folder would be at its most wrong here.
    """
    real = models.Path.write_text

    def refuse(self, *args, **kwargs):
        if self.name == "model.json":
            raise OSError("read-only file system")
        return real(self, *args, **kwargs)

    monkeypatch.setattr(models.Path, "write_text", refuse)

    _, out = run(capsys, monkeypatch, ["2"])

    assert "could not remember this choice" in out.err
    assert "remembering this choice in" not in out.out
    assert axiom_dir.exists(), "the folder was not created, so this tested nothing"
    assert not (axiom_dir / "model.json").exists()

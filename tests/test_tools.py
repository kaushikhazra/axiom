"""The tools themselves: what they declare, and what running one does.

No model and no backend here. Everything writes inside pytest's tmp_path -
the security stories have not landed, so nothing outside it is touched.
"""

import inspect

from axiom import tools


def test_every_registered_tool_is_declared_once():
    declared = tools.declarations()
    assert len(declared) == len(tools.REGISTRY)
    assert {d["function"]["name"] for d in declared} == set(tools.REGISTRY)


def test_a_declaration_is_shaped_the_way_a_model_is_given_it():
    declaration = tools.declarations()[0]
    assert declaration["type"] == "function"
    function = declaration["function"]
    assert set(function) == {"name", "description", "parameters"}
    assert function["parameters"]["type"] == "object"
    assert function["description"], (
        "a tool the model cannot understand will not be used"
    )


def test_declarations_do_not_depend_on_the_model():
    """AC 4: one shape for every model.

    A declarations() that took a model would be the first step towards a
    per-model branch, which is the thing #34 exists to avoid.
    """
    assert inspect.signature(tools.declarations).parameters == {}


def test_read_file_returns_what_is_in_the_file(tmp_path):
    target = tmp_path / "notes.txt"
    target.write_text("Biscuit the cat is ginger.\n", encoding="utf-8")

    assert (
        tools.run("read_file", {"path": str(target)}) == "Biscuit the cat is ginger.\n"
    )


def test_an_empty_file_reads_as_empty_not_as_a_failure(tmp_path):
    """AC 25: empty is an answer. Reporting it as an error would send the
    model looking for a problem that is not there."""
    target = tmp_path / "empty.txt"
    target.write_text("", encoding="utf-8")

    result = tools.run("read_file", {"path": str(target)})

    assert result == ""
    assert "error" not in result


def test_a_missing_file_explains_itself(tmp_path):
    """AC 24: the model is told plainly, and nothing raises."""
    result = tools.run("read_file", {"path": str(tmp_path / "nope.txt")})

    assert result.startswith("error:")
    assert "nope.txt" in result


def test_an_unknown_tool_is_named_rather_than_raising():
    """AC 29: a call axiom cannot make sense of does not end the turn."""
    result = tools.run("summon_daemon", {"x": 1})

    assert result.startswith("error:")
    assert "summon_daemon" in result


def test_wrong_arguments_are_reported_rather_than_raising():
    """AC 29: models do get parameter names wrong."""
    result = tools.run("read_file", {"filename": "/somewhere"})

    assert result.startswith("error:")
    assert "read_file" in result


def test_missing_arguments_are_reported_rather_than_raising():
    result = tools.run("read_file", {})

    assert result.startswith("error:")


def test_running_a_tool_never_raises(tmp_path):
    """The turn loop calls this without a try - anything escaping would end
    the session, which is exactly what AC 28 forbids."""
    for name, arguments in [
        ("read_file", {"path": str(tmp_path)}),  # a directory, not a file
        ("read_file", {"path": ""}),
        ("read_file", {"path": None}),
        ("nope", {}),
    ]:
        assert tools.run(name, arguments).startswith("error:")


def test_writing_a_file_creates_it_and_names_the_path(tmp_path):
    """AC 9."""
    target = tmp_path / "new.txt"

    result = tools.run("write_file", {"path": str(target), "content": "hello"})

    assert target.read_text(encoding="utf-8") == "hello"
    assert str(target) in result


def test_writing_creates_missing_parent_directories(tmp_path):
    target = tmp_path / "deep" / "deeper" / "new.txt"

    tools.run("write_file", {"path": str(target), "content": "hello"})

    assert target.read_text(encoding="utf-8") == "hello"


def test_an_edit_leaves_every_other_byte_alone(tmp_path):
    """AC 11: changing part of a file leaves the rest byte-identical.

    Checked as exact bytes, line endings included - an edit that rewrote the
    whole file would satisfy a looser comparison.
    """
    target = tmp_path / "three.txt"
    target.write_bytes(b"first line\r\nsecond line\r\nthird line\r\n")

    result = tools.run(
        "edit_file",
        {"path": str(target), "old": "second line", "new": "CHANGED"},
    )

    assert target.read_bytes() == b"first line\r\nCHANGED\r\nthird line\r\n"
    assert "replaced one occurrence" in result


def test_an_edit_refuses_text_that_appears_more_than_once(tmp_path):
    """Changing three things when one was described is a different edit."""
    target = tmp_path / "repeated.txt"
    target.write_text("a\na\na\n", encoding="utf-8")

    result = tools.run("edit_file", {"path": str(target), "old": "a", "new": "b"})

    assert result.startswith("error:")
    assert "3 times" in result
    assert target.read_text(encoding="utf-8") == "a\na\na\n", "the file was touched"


def test_an_edit_refuses_text_that_is_not_there(tmp_path):
    target = tmp_path / "plain.txt"
    target.write_text("hello\n", encoding="utf-8")

    result = tools.run("edit_file", {"path": str(target), "old": "absent", "new": "x"})

    assert result.startswith("error:")
    assert target.read_text(encoding="utf-8") == "hello\n"


def test_deleting_a_file_removes_it_and_says_so(tmp_path):
    """AC 12. Called directly - a live model is never asked to improvise its
    way to a delete while no security layer exists."""
    target = tmp_path / "doomed.txt"
    target.write_text("goodbye", encoding="utf-8")

    result = tools.run("delete_file", {"path": str(target)})

    assert not target.exists()
    assert str(target) in result


def test_deleting_something_that_is_not_there_explains_itself(tmp_path):
    result = tools.run("delete_file", {"path": str(tmp_path / "ghost.txt")})

    assert result.startswith("error:")


def test_an_argument_the_tool_never_declared_is_refused():
    """A model cannot reach a keyword the schema does not offer it."""
    result = tools.run("run_command", {"command": "echo hi", "timeout": 99999})

    assert result.startswith("error:")
    assert "timeout" in result

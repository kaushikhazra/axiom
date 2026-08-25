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

"""Models that can call tools are offered before models that cannot.

#52, which changes the order #48 established and therefore has to leave every
other criterion of #48 and #49 standing. The interesting cases are the two
where the order does *nothing* - every model capable, or none - and the one
where the order must not be paid for at all.
"""

import json

import pytest

from axiom import backend, main, models
from conftest import StubBackend, feed, listed, row_for


HOST = "http://localhost:11434"

# As the local host has them. `gemma2:2b` is alphabetically first and is the
# one model that cannot call tools - which is the whole reason this exists.
INSTALLED = ["gemma2:2b", "qwen2.5-coder:7b", "gemma4:e2b", "ornith:9b", "qwen2.5:7b"]
REAL = {
    "gemma2:2b": False,
    "gemma4:e2b": True,
    "ornith:9b": True,
    "qwen2.5:7b": True,
    "qwen2.5-coder:7b": True,
}
# Tool-capable first, each group in name order.
EXPECTED = (
    "gemma4:e2b",
    "ornith:9b",
    "qwen2.5-coder:7b",
    "qwen2.5:7b",
    "gemma2:2b",
)


@pytest.fixture
def choice(tmp_path, monkeypatch):
    where = tmp_path / ".axiom" / "model.json"
    monkeypatch.setattr(models, "DEFAULT_CHOICE_FILE", where)
    return where


def rows(text):
    """The model names, in the order the list printed them.

    `listed` since #77 - the list is inside a border now, and a parser of its own
    here was one of four that all keyed on "the line starts with a digit".
    """
    return listed(text)


def run(capsys, monkeypatch, typed=None, tty=True, argv=None, **stub):
    monkeypatch.setattr("sys.stdin.isatty", lambda: tty)
    stub.setdefault("models", INSTALLED)
    stub.setdefault("capable", REAL)
    made = StubBackend(**stub)
    feed(monkeypatch, [*(typed or []), "/exit"])
    main(argv or [], using=made)
    return made, capsys.readouterr()


# --- The order -----------------------------------------------------------


def test_tool_capable_models_come_first(capsys, monkeypatch, choice):
    """AC 1, AC 2."""
    _, out = run(capsys, monkeypatch, ["1"])

    assert rows(out.out) == list(EXPECTED)


def test_within_each_group_the_order_is_by_name(capsys, monkeypatch, choice):
    """AC 2."""
    _, out = run(capsys, monkeypatch, ["1"])
    shown = rows(out.out)

    can = [m for m in shown if REAL[m]]
    cannot = [m for m in shown if not REAL[m]]
    assert can == sorted(can, key=str.lower)
    assert cannot == sorted(cannot, key=str.lower)


def test_the_order_is_the_same_on_the_next_run(capsys, monkeypatch, choice):
    """AC 3. Both keys are properties of the model, not of the moment."""
    _, first = run(capsys, monkeypatch, ["1"])
    _, second = run(capsys, monkeypatch, ["1"], models=list(reversed(INSTALLED)))

    assert rows(first.out) == rows(second.out) == list(EXPECTED)


def test_with_every_model_capable_the_order_is_plain_name_order(
    capsys, monkeypatch, choice
):
    """AC 4."""
    _, out = run(capsys, monkeypatch, ["1"], capable=dict.fromkeys(INSTALLED, True))

    assert rows(out.out) == sorted(INSTALLED, key=str.lower)


def test_with_no_model_capable_the_order_is_plain_name_order(
    capsys, monkeypatch, choice
):
    """AC 4."""
    _, out = run(capsys, monkeypatch, ["1"], capable=dict.fromkeys(INSTALLED, False))

    assert rows(out.out) == sorted(INSTALLED, key=str.lower)


def test_the_sort_needs_no_backend_at_all():
    """AC 1, AC 4 at the seam, where the two keys can be seen separately."""
    assert models.sorted_models(INSTALLED, {"ornith:9b"})[0] == "ornith:9b"
    assert models.sorted_models(INSTALLED, set()) == models.sorted_models(INSTALLED)
    assert models.sorted_models(INSTALLED, set(INSTALLED)) == models.sorted_models(
        INSTALLED
    )


# --- What that changes about being chosen for ----------------------------


def test_the_default_is_a_model_that_can_call_tools(capsys, monkeypatch, choice):
    """AC 5. The whole point: `gemma2:2b` no longer takes the mark."""
    _, out = run(capsys, monkeypatch, ["1"])

    assert row_for(out.out, "gemma4:e2b").endswith("tools  (default)")
    assert not row_for(out.out, "gemma2:2b").endswith("(default)")


def test_a_piped_run_settles_on_a_model_that_can_call_tools(
    capsys, monkeypatch, choice
):
    """AC 6. Every piped run with nothing chosen used to land on gemma2:2b."""
    _, out = run(capsys, monkeypatch, tty=False)

    assert "using gemma4:e2b - first installed" in out.out


def test_a_named_model_is_not_overridden(capsys, monkeypatch, choice):
    """AC 7. Naming a tool-less model is a choice, not a mistake to correct."""
    stub, out = run(capsys, monkeypatch, argv=["--model", "gemma2:2b"])

    assert f"axiom: gemma2:2b at {HOST}" in out.out


def test_a_remembered_model_is_not_overridden(capsys, monkeypatch, choice):
    """AC 7."""
    choice.parent.mkdir(parents=True)
    choice.write_text(json.dumps({HOST: "gemma2:2b"}), encoding="utf-8")

    _, out = run(capsys, monkeypatch, tty=False)

    assert "using gemma2:2b - your last choice here" in out.out


def test_a_remembered_model_still_takes_the_mark_in_the_list(
    capsys, monkeypatch, choice
):
    """AC 7, interactively - the mark follows the user, not the capability."""
    choice.parent.mkdir(parents=True)
    choice.write_text(json.dumps({HOST: "gemma2:2b"}), encoding="utf-8")

    _, out = run(capsys, monkeypatch, [""])

    assert row_for(out.out, "gemma2:2b").endswith("(default)")
    assert f"axiom: gemma2:2b at {HOST}" in out.out


# --- Seeing why ----------------------------------------------------------


def test_the_list_says_which_models_can_call_tools(capsys, monkeypatch, choice):
    """AC 8."""
    _, out = run(capsys, monkeypatch, ["1"])

    assert "tools" in row_for(out.out, "gemma4:e2b")
    assert "tools" not in row_for(out.out, "gemma2:2b")


def test_nothing_is_annotated_when_it_would_explain_nothing(
    capsys, monkeypatch, choice
):
    """AC 8. A note on every row explains nothing and lengthens every row."""
    _, out = run(capsys, monkeypatch, ["1"], capable=dict.fromkeys(INSTALLED, True))

    assert "tools" not in "\n".join(rows(out.out))
    assert "  tools" not in out.out.split("which model?")[0].split("models on")[1]


def test_a_host_where_nothing_can_call_tools_says_so(capsys, monkeypatch, choice):
    """AC 9."""
    _, out = run(capsys, monkeypatch, ["1"], capable=dict.fromkeys(INSTALLED, False))

    assert "none of these can call tools" in out.out


# --- Cost ----------------------------------------------------------------


def test_naming_an_installed_model_never_asks_what_anything_can_do(
    capsys, monkeypatch, choice
):
    """AC 10, and the reason `choose` takes a callable rather than a set.

    Establishing tool support is one request per model. A run that names a
    model that exists shows no list and falls back to nothing, so it must not
    pay - and the only way to see that it did not is to see it was never asked.
    """
    stub, _ = run(capsys, monkeypatch, argv=["--model", "ornith:9b"])

    assert stub.capability_asks == []


def test_a_single_installed_model_never_asks_either(capsys, monkeypatch, choice):
    """AC 10. One model is one model in any order."""
    stub, _ = run(capsys, monkeypatch, models=["solo:1b"], capable={"solo:1b": True})

    assert stub.capability_asks == []


def test_a_remembered_model_in_a_piped_run_never_asks_either(
    capsys, monkeypatch, choice
):
    """AC 10. The user's own choice needs no ordering to find it."""
    choice.parent.mkdir(parents=True)
    choice.write_text(json.dumps({HOST: "ornith:9b"}), encoding="utf-8")

    stub, _ = run(capsys, monkeypatch, tty=False)

    assert stub.capability_asks == []


def test_the_question_is_asked_once_and_covers_every_model(capsys, monkeypatch, choice):
    """AC 11."""
    stub, _ = run(capsys, monkeypatch, ["1"])

    assert len(stub.capability_asks) == 1
    assert sorted(stub.capability_asks[0]) == sorted(INSTALLED)


# --- Failure -------------------------------------------------------------


class Silent(StubBackend):
    """A host that lists models but cannot say what any of them can do."""

    def tool_capable(self, models):  # noqa: ANN001
        self.capability_asks.append(list(models))
        return set()


def test_a_model_whose_support_is_unknown_is_still_offered(capsys, monkeypatch, choice):
    """AC 12. Unknown is ordered as "cannot", and nothing is claimed for it."""
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    stub = Silent(models=INSTALLED)
    feed(monkeypatch, ["2", "/exit"])
    main([], using=stub)
    out = capsys.readouterr()

    assert rows(out.out) == sorted(INSTALLED, key=str.lower)
    assert "  tools" not in out.out
    # Still choosable, and the session starts on it.
    assert f"axiom: {sorted(INSTALLED, key=str.lower)[1]} at {HOST}" in out.out


def test_a_failure_to_establish_support_never_ends_the_run(capsys, monkeypatch, choice):
    """AC 13."""
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    stub = Silent(models=INSTALLED)
    feed(monkeypatch, ["1", "hello", "/exit"])

    main([], using=stub)

    assert stub.streamed, "the run ended instead of carrying on"


def test_the_real_backend_treats_an_unaskable_model_as_not_capable():
    """AC 12 at the seam, without a host.

    `tool_capable` swallows per model, unlike `installed` which raises: a
    model that cannot be asked is a gap in what is known, not a reason to
    refuse the whole list.
    """

    class Refusing:
        def show(self, model):
            if model == "broken:1b":
                raise ConnectionError("no")
            return type("Info", (), {"capabilities": ["completion", "tools"]})()

    real = backend.OllamaBackend.__new__(backend.OllamaBackend)
    real._client = Refusing()

    assert real.tool_capable(["fine:1b", "broken:1b"]) == {"fine:1b"}

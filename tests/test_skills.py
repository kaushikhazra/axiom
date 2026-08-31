"""What loads as a skill, and what a skill costs before it is invoked.

The rule this feature turns on is that a catalogued skill costs one line on
every request and its instructions cost nothing until they are wanted. So the
test that matters here is not that `catalogue_text` looks right - it is that
the instructions are absent from what is actually handed to the model. That one
asserts on `StubBackend.streamed`, which is the real payload, and it will fail
if any later cycle decides to helpfully include "a bit of context" from a body.
"""

import re

import pytest

from axiom import compaction, main, models, skills, tools
from conftest import StubBackend, feed


def write_skill(
    directory, folder, *, name=None, description=None, body="Do the thing.", extra=""
):
    """A skill on disk, as a user would have written it by hand."""
    made = directory / folder
    made.mkdir(parents=True, exist_ok=True)
    lines = ["---"]
    if name is not None:
        lines.append(f"name: {name}")
    if description is not None:
        lines.append(f"description: {description}")
    if extra:
        lines.append(extra)
    lines.extend(["---", "", body])
    (made / "SKILL.md").write_text("\n".join(lines), encoding="utf-8")
    return made


# -- what loads ---------------------------------------------------------------


def test_a_skill_is_a_folder_with_a_skill_file(tmp_path):
    """AC 23 - name and description from the frontmatter, instructions behind it."""
    write_skill(
        tmp_path, "tests", name="writing-tests", description="How we write tests"
    )

    found = skills.read(tmp_path)

    assert found.names == ("writing-tests",)
    assert found.skills[0].description == "How we write tests"
    assert not found.problems


def test_no_directory_is_not_a_problem(tmp_path):
    """AC 1 - a project with no skills is the ordinary case, not a misconfiguration."""
    found = skills.read(tmp_path / "nothing-here")

    assert found.names == ()
    assert found.problems == ()


def test_an_empty_directory_behaves_exactly_as_no_directory(tmp_path):
    """AC 30 - the same answer, down to the problems, which is what "exactly" means."""
    (tmp_path / "skills").mkdir()

    assert skills.read(tmp_path / "skills") == skills.read(tmp_path / "nothing-here")


def test_a_foreign_skill_file_loads_unchanged(tmp_path):
    """AC 24 - fields axiom does not use are ignored rather than refused.

    The interop criterion. A SKILL.md written for another agent carries keys
    axiom has never heard of, and refusing one would break the promise for no
    gain.
    """
    write_skill(
        tmp_path,
        "borrowed",
        name="review",
        description="Review a diff",
        extra="allowed-tools: Read, Grep\nlicense: MIT\nmodel: opus",
    )

    found = skills.read(tmp_path)

    assert found.names == ("review",)
    assert not found.problems


# -- what does not load, and what the user is told ----------------------------


def test_a_folder_with_no_skill_file_is_reported_and_skipped(tmp_path):
    """AC 26."""
    (tmp_path / "empty").mkdir()

    found = skills.read(tmp_path)

    assert found.names == ()
    assert "empty has no SKILL.md" in found.problems


def test_a_skill_with_no_instructions_is_reported_and_not_offered(tmp_path):
    """AC 27 - a description with nothing behind it is a promise invoking cannot keep."""
    write_skill(tmp_path, "hollow", name="hollow", description="Sounds useful", body="")

    found = skills.read(tmp_path)

    assert found.names == ()
    assert "hollow has no instructions" in found.problems


def test_a_missing_field_is_named(tmp_path):
    """AC 4 - the reason sends the user to one line, not back to the whole file."""
    write_skill(tmp_path, "nameless", description="Has no name")

    found = skills.read(tmp_path)

    assert "nameless has no name" in found.problems


def test_frontmatter_that_cannot_be_parsed_is_reported(tmp_path):
    """AC 4, AC 40 - a broken skill costs that skill, with a reason."""
    made = tmp_path / "broken"
    made.mkdir()
    (made / "SKILL.md").write_text("---\nname: [unclosed\n---\nbody", encoding="utf-8")

    found = skills.read(tmp_path)

    assert found.names == ()
    assert any("broken" in problem for problem in found.problems)


def test_one_bad_skill_does_not_cost_the_others(tmp_path):
    """AC 4 - every other skill still loads and the session continues."""
    write_skill(tmp_path, "good", name="good", description="Fine")
    (tmp_path / "bad").mkdir()

    found = skills.read(tmp_path)

    assert found.names == ("good",)
    assert len(found.problems) == 1


def test_two_skills_claiming_one_name_report_which_was_used(tmp_path):
    """AC 28 - the user's next question is which of the two they just ran."""
    write_skill(tmp_path, "alpha", name="review", description="First")
    write_skill(tmp_path, "beta", name="review", description="Second")

    found = skills.read(tmp_path)

    assert found.names == ("review",)
    assert found.skills[0].description == "First"
    assert any("alpha" in problem and "beta" in problem for problem in found.problems)


# -- instructions are read when they are wanted, not before -------------------


def test_instructions_are_read_at_invocation_not_at_load(tmp_path):
    """AC 33 - an edit during the run takes effect without a restart.

    Loading everything at startup is simpler and makes this criterion quietly
    false while every other test still passes. This is the one that notices.
    """
    made = write_skill(
        tmp_path, "edited", name="edited", description="d", body="Original."
    )
    found = skills.read(tmp_path)

    (made / "SKILL.md").write_text(
        "---\nname: edited\ndescription: d\n---\n\nRewritten.", encoding="utf-8"
    )

    assert skills.instructions(found.skills[0]) == "Rewritten."


def test_a_skill_removed_since_startup_says_so(tmp_path):
    """AC 41 - says so rather than handing back something stale."""
    made = write_skill(tmp_path, "doomed", name="doomed", description="d")
    found = skills.read(tmp_path)

    (made / "SKILL.md").unlink()
    result = skills.instructions(found.skills[0])

    assert result.startswith("error:")
    assert "doomed" in result


# -- the catalogue, and what it costs -----------------------------------------


def test_the_catalogue_carries_the_description_and_not_the_instructions(tmp_path):
    """AC 12 - at the level of the string that gets appended to the prompt."""
    write_skill(
        tmp_path,
        "secret",
        name="secret",
        description="A description",
        body="INSTRUCTIONS-THAT-MUST-NOT-TRAVEL",
    )

    text = skills.catalogue_text(skills.read(tmp_path))

    assert "A description" in text
    assert "INSTRUCTIONS-THAT-MUST-NOT-TRAVEL" not in text


def test_no_skills_adds_nothing_at_all_to_the_prompt(tmp_path):
    """AC 1, AC 38 - not a heading with nothing under it. Nothing."""
    assert skills.catalogue_text(skills.read(tmp_path)) == ""
    assert tools.system_prompt(tools.Limits(), "") == tools.system_prompt(
        tools.Limits()
    )


# -- and the same thing, asserted on what is actually sent --------------------


@pytest.fixture(autouse=True)
def choice(tmp_path, monkeypatch):
    monkeypatch.setattr(
        models, "DEFAULT_CHOICE_FILE", tmp_path / ".axiom" / "model.json"
    )


def run(capsys, monkeypatch, tmp_path, skills_directory, typed=(), **stub):
    """A whole session, with the catalogue pointed at a directory of our own."""
    monkeypatch.setattr(skills, "DEFAULT_SKILLS_DIRECTORY", skills_directory)
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    stub.setdefault("models", ["big:70b"])
    made = StubBackend(**stub)
    feed(monkeypatch, [*typed, "/exit"])
    main(["--model", "big:70b"], using=made)
    return made, capsys.readouterr()


def everything_sent(backend) -> str:
    """Every byte that reached the model, as one string to search."""
    return "\n".join(
        message.get("content") or "" for turn in backend.streamed for message in turn
    )


def test_a_skills_body_never_reaches_the_model_until_it_is_invoked(
    capsys, monkeypatch, tmp_path
):
    """AC 13, and the criterion the whole feature turns on.

    Asserted on what was streamed rather than on `catalogue_text`, deliberately.
    The failure this guards is a later cycle deciding to include the first few
    lines of each body "for context" - which would look like a feature, would
    keep every other test green, and would make every request more expensive
    forever.
    """
    directory = tmp_path / "skills"
    write_skill(
        directory,
        "writing",
        name="writing-tests",
        description="How this repo writes tests",
        body="NEVER-SEND-ME: always use pytest and never mock the filesystem.",
    )

    made, _ = run(capsys, monkeypatch, tmp_path, directory, typed=["hello"])
    sent = everything_sent(made)

    assert "writing-tests" in sent
    assert "How this repo writes tests" in sent
    assert "NEVER-SEND-ME" not in sent


def test_the_catalogue_is_what_the_cost_line_counts(capsys, monkeypatch, tmp_path):
    """AC 3 - the reported cost includes the skills, weighed the same way.

    Derived rather than hard-coded, for the reason `test_tool_cost` gives: the
    standing prompt has been quoted at three different numbers by three routes,
    and a better figure that contradicts the compaction it explains is worse
    than none.
    """
    directory = tmp_path / "skills"
    write_skill(directory, "one", name="one", description="x" * 200)

    with_skill, out = run(capsys, monkeypatch, tmp_path, directory)
    reported = int(re.search(r"tools cost about (\d+) tokens", out.out).group(1))

    bare = compaction.estimated_tokens(
        [{"role": "system", "content": tools.system_prompt(tools.Limits())}]
    )
    catalogued = compaction.estimated_tokens(
        [
            {
                "role": "system",
                "content": tools.system_prompt(
                    tools.Limits(), skills.catalogue_text(skills.read(directory))
                ),
            }
        ]
    )

    assert catalogued > bare
    assert reported >= catalogued - bare

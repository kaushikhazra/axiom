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
from axiom.backend import Call
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


# -- the four tools -----------------------------------------------------------

VALID = "---\nname: {name}\ndescription: {description}\n---\n\n{body}\n"


def library(tmp_path):
    return skills.Library(tmp_path / "skills")


def test_read_returns_the_file_including_its_frontmatter(tmp_path):
    """AC 17 - read is for editing, which needs the frontmatter invoke never sends."""
    write_skill(tmp_path / "skills", "one", name="one", description="d", body="Steps.")

    got = library(tmp_path).source("one")

    assert "name: one" in got
    assert "Steps." in got


def test_invoke_returns_the_instructions_and_nothing_else(tmp_path):
    """AC 13 - the frontmatter is catalogue material and does not travel again."""
    write_skill(tmp_path / "skills", "one", name="one", description="d", body="Steps.")

    got = library(tmp_path).invoke("one")

    assert got == "Steps."
    assert "description" not in got


def test_a_written_skill_is_catalogued_at_once(tmp_path):
    """AC 18 - available in the same session, without a restart.

    Asserted on the catalogue rather than on the file. A test that writes and
    then reads the file back passes whether or not the refresh happened, which
    is the vacuous shape this criterion invites.
    """
    made = library(tmp_path)
    assert made.catalogue.names == ()

    made.write("fresh", VALID.format(name="fresh", description="New", body="Do it."))

    assert made.catalogue.names == ("fresh",)
    assert made.invoke("fresh") == "Do it."


def test_writing_over_a_skill_changes_what_the_model_is_told(tmp_path):
    """AC 19 - the replacement is what is used from then on.

    The description is what reaches the model in the catalogue, so that is what
    this asserts on. Checking the file would prove the write and not the
    replacement.
    """
    made = library(tmp_path)
    made.write("one", VALID.format(name="one", description="First", body="A."))
    made.write("one", VALID.format(name="one", description="Second", body="B."))

    assert [s.description for s in made.catalogue.skills] == ["Second"]
    assert made.invoke("one") == "B."


def test_a_deleted_skill_leaves_the_catalogue_at_once(tmp_path):
    """AC 20."""
    write_skill(tmp_path / "skills", "gone", name="gone", description="d")
    made = library(tmp_path)

    made.delete("gone")

    assert made.catalogue.names == ()
    assert made.invoke("gone").startswith("error:")


def test_a_write_with_no_description_is_refused_and_names_the_field(tmp_path):
    """AC 21 - the refusal names what is wrong, and nothing is written."""
    made = library(tmp_path)

    result = made.write("bad", "---\nname: bad\n---\n\nSome instructions.\n")

    assert result.startswith("error:")
    assert "description" in result
    assert made.catalogue.names == ()
    assert not (tmp_path / "skills" / "bad").exists()


def test_a_refused_write_leaves_the_previous_version_untouched(tmp_path):
    """AC 42 - by construction: validation happens before the file is opened."""
    made = library(tmp_path)
    made.write("one", VALID.format(name="one", description="Good", body="Keep me."))

    result = made.write("one", "---\nname: one\n---\n\nno description\n")

    assert result.startswith("error:")
    assert made.invoke("one") == "Keep me."
    assert made.catalogue.find("one").description == "Good"


def test_a_hand_written_skill_and_a_written_one_behave_the_same(tmp_path):
    """AC 22."""
    write_skill(
        tmp_path / "skills", "byhand", name="byhand", description="d", body="X."
    )
    made = library(tmp_path)
    made.write("bytool", VALID.format(name="bytool", description="d", body="X."))

    assert made.invoke("byhand") == made.invoke("bytool")
    assert sorted(made.catalogue.names) == ["byhand", "bytool"]


def test_an_unknown_skill_is_named_with_what_there_is_instead(tmp_path):
    """AC 10's shape at the tool level - a model that got the name nearly right
    can correct itself, where "no such skill" sends it back to memory."""
    write_skill(tmp_path / "skills", "one", name="one", description="d")

    result = library(tmp_path).invoke("onee")

    assert "onee" in result
    assert "one" in result


def test_a_skill_tool_without_a_library_says_so(tmp_path):
    """AC 38, AC 43 - not a crash and not silence."""
    assert tools.run("invoke_skill", {"name": "x"}) == tools.NO_SKILLS
    assert tools.run("write_skill", {"name": "x", "content": "y"}) == tools.NO_SKILLS


# -- what is offered, and what it costs ---------------------------------------


def offered_names(made) -> set:
    """The tool names actually sent to the model on the last turn."""
    sent = [offered for offered in made.tools_sent if offered]
    return {tool["function"]["name"] for tool in sent[-1]} if sent else set()


def test_an_empty_catalogue_is_not_offered_the_tools_it_cannot_use(
    capsys, monkeypatch, tmp_path
):
    """AC 1 - a run with no skills starts as it does today.

    Measured: the four skill tools cost 396 tokens per request, taking the total
    from 1111 to 1507. Three of them can do nothing against an empty catalogue.
    """
    made, _ = run(capsys, monkeypatch, tmp_path, tmp_path / "none", typed=["hello"])

    names = offered_names(made)
    assert "write_skill" in names, "the first skill could never be written"
    assert not names & {"read_skill", "delete_skill", "invoke_skill"}


def test_a_catalogue_with_a_skill_is_offered_all_four(capsys, monkeypatch, tmp_path):
    """The other direction - without this the test above passes by offering nothing."""
    directory = tmp_path / "skills"
    write_skill(directory, "one", name="one", description="d")

    made, _ = run(capsys, monkeypatch, tmp_path, directory, typed=["hello"])

    assert {
        "read_skill",
        "delete_skill",
        "invoke_skill",
        "write_skill",
    } <= offered_names(made)


def test_writing_the_first_skill_brings_invoke_into_existence(
    capsys, monkeypatch, tmp_path
):
    """The sequence the gating is most likely to break.

    A session that starts empty is not offered `invoke_skill` at all. Writing
    the first skill of a project therefore has to bring the tool into being, or
    the model is told about a skill it has no way to call - a dead end that
    every unit test of the library would miss, because the library is not what
    decides what is offered.
    """
    directory = tmp_path / "skills"
    made, _ = run(
        capsys,
        monkeypatch,
        tmp_path,
        directory,
        typed=["make one", "now use it"],
        turns=[
            [
                Call(
                    "write_skill",
                    {
                        "name": "fresh",
                        "content": VALID.format(
                            name="fresh", description="New", body="Do it."
                        ),
                    },
                )
            ],
            ["made it"],
            ["used it"],
        ],
    )

    assert "invoke_skill" in offered_names(made), (
        "the skill it just wrote is unreachable"
    )
    assert "fresh" in everything_sent(made), "the new skill never reached the catalogue"


# -- the two commands ---------------------------------------------------------


def turns_taken(made) -> int:
    """How many times the model was actually asked anything."""
    return len(made.streamed)


def test_skills_lists_every_loaded_skill_with_its_description(
    capsys, monkeypatch, tmp_path
):
    """AC 5 - one to a line, name and description."""
    directory = tmp_path / "skills"
    write_skill(directory, "a", name="alpha", description="The first one")
    write_skill(directory, "b", name="beta", description="The second one")

    made, out = run(capsys, monkeypatch, tmp_path, directory, typed=["/skills"])

    assert "alpha - The first one" in out.out
    assert "beta - The second one" in out.out
    assert turns_taken(made) == 0, "listing asked the model something"


def test_skills_with_none_loaded_says_so_and_says_where_they_go(
    capsys, monkeypatch, tmp_path
):
    """AC 6 - both halves. The path is the only line telling a new user how to start."""
    directory = tmp_path / "skills"

    _, out = run(capsys, monkeypatch, tmp_path, directory, typed=["/skills"])

    assert "no skills loaded" in out.out
    assert str(directory) in out.out
    assert "SKILL.md" in out.out


def test_skill_puts_the_instructions_in_and_starts_a_turn(
    capsys, monkeypatch, tmp_path
):
    """AC 7 - both halves. The break that matters is loading without asking."""
    directory = tmp_path / "skills"
    write_skill(
        directory, "one", name="one", description="d", body="FOLLOW-THESE-STEPS"
    )

    made, out = run(capsys, monkeypatch, tmp_path, directory, typed=["/skill one"])

    assert turns_taken(made) == 1, "the instructions were loaded but nothing was asked"
    assert "FOLLOW-THESE-STEPS" in everything_sent(made)
    assert "skill: one" in out.out


def test_skill_with_trailing_text_takes_it_as_the_request(
    capsys, monkeypatch, tmp_path
):
    """AC 8 - the skill is context, the trailing text is what was asked."""
    directory = tmp_path / "skills"
    write_skill(directory, "one", name="one", description="d", body="THE-INSTRUCTIONS")

    made, _ = run(
        capsys, monkeypatch, tmp_path, directory, typed=["/skill one cover the parser"]
    )

    sent = everything_sent(made)
    assert "THE-INSTRUCTIONS" in sent
    assert "cover the parser" in sent
    assert sent.index("THE-INSTRUCTIONS") < sent.index("cover the parser")


def test_skill_with_no_name_lists_and_sends_nothing(capsys, monkeypatch, tmp_path):
    """AC 9 - and the half a screenshot cannot check is the second assertion."""
    directory = tmp_path / "skills"
    write_skill(directory, "one", name="one", description="d")

    made, out = run(capsys, monkeypatch, tmp_path, directory, typed=["/skill"])

    assert "one" in out.out
    assert turns_taken(made) == 0, "nothing should have been sent to the model"


def test_an_unknown_skill_lists_and_sends_nothing(capsys, monkeypatch, tmp_path):
    """AC 10 - same shape, and the same half that is easy to miss."""
    directory = tmp_path / "skills"
    write_skill(directory, "one", name="one", description="d")

    made, out = run(capsys, monkeypatch, tmp_path, directory, typed=["/skill nope"])

    assert "no skill named nope" in out.out
    assert "one" in out.out
    assert turns_taken(made) == 0, "nothing should have been sent to the model"


def test_skills_is_not_read_as_skill_with_an_argument(capsys, monkeypatch, tmp_path):
    """The command names overlap, and the wrong order makes /skills unreachable."""
    directory = tmp_path / "skills"
    write_skill(directory, "one", name="one", description="d")

    made, out = run(capsys, monkeypatch, tmp_path, directory, typed=["/skills"])

    assert "no skill named s" not in out.out
    assert turns_taken(made) == 0


# -- the off switch, and what startup says ------------------------------------


def run_argv(
    capsys, monkeypatch, tmp_path, skills_directory, argv=(), typed=(), **stub
):
    """A session with extra command-line arguments."""
    monkeypatch.setattr(skills, "DEFAULT_SKILLS_DIRECTORY", skills_directory)
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    stub.setdefault("models", ["big:70b"])
    made = StubBackend(**stub)
    feed(monkeypatch, [*typed, "/exit"])
    main([*argv, "--model", "big:70b"], using=made)
    return made, capsys.readouterr()


def test_skills_are_on_by_default(capsys, monkeypatch, tmp_path):
    """AC 36."""
    directory = tmp_path / "skills"
    write_skill(directory, "one", name="one", description="Some description")

    made, out = run_argv(capsys, monkeypatch, tmp_path, directory, typed=["hello"])

    assert "Some description" in everything_sent(made)
    assert "1 skill loaded" in out.out


def test_the_flag_turns_skills_off(capsys, monkeypatch, tmp_path):
    """AC 37, AC 38 - nothing about any skill reaches the model."""
    directory = tmp_path / "skills"
    write_skill(directory, "one", name="one", description="Some description")

    made, out = run_argv(
        capsys, monkeypatch, tmp_path, directory, argv=["--no-skills"], typed=["hello"]
    )

    sent = everything_sent(made)
    assert "Some description" not in sent
    assert skills.catalogue_text(skills.read(directory)) not in sent
    assert "skills off" in out.out


def test_the_variable_turns_skills_off(capsys, monkeypatch, tmp_path):
    """AC 37 - the environment variable, on its own."""
    directory = tmp_path / "skills"
    write_skill(directory, "one", name="one", description="Some description")
    monkeypatch.setenv("AXIOM_SKILLS", "off")

    made, _ = run_argv(capsys, monkeypatch, tmp_path, directory, typed=["hello"])

    assert "Some description" not in everything_sent(made)


def test_the_flag_wins_over_the_variable(capsys, monkeypatch, tmp_path):
    """AC 37 - precedence, stated as a criterion and therefore tested as one."""
    directory = tmp_path / "skills"
    write_skill(directory, "one", name="one", description="Some description")
    monkeypatch.setenv("AXIOM_SKILLS", "on")

    made, _ = run_argv(
        capsys, monkeypatch, tmp_path, directory, argv=["--no-skills"], typed=["hello"]
    )

    assert "Some description" not in everything_sent(made)


def test_with_skills_off_the_cost_is_not_paid(capsys, monkeypatch, tmp_path):
    """AC 38's third clause - the one that gets faked.

    An off switch that hides the line but still declares the tools would pass a
    test written against the message. This asserts on what was declared.
    """
    directory = tmp_path / "skills"
    write_skill(directory, "one", name="one", description="d")

    off, _ = run_argv(
        capsys, monkeypatch, tmp_path, directory, argv=["--no-skills"], typed=["hi"]
    )

    assert not offered_names(off) & tools.SKILL_TOOLS


def test_with_skills_off_the_commands_say_so(capsys, monkeypatch, tmp_path):
    """AC 38's second clause - and not "no skills loaded", which would be a lie."""
    directory = tmp_path / "skills"
    write_skill(directory, "one", name="one", description="d")

    made, out = run_argv(
        capsys,
        monkeypatch,
        tmp_path,
        directory,
        argv=["--no-skills"],
        typed=["/skills", "/skill one"],
    )

    assert "skills are off for this run" in out.out
    assert "no skills loaded" not in out.out
    assert turns_taken(made) == 0


def test_the_startup_line_says_how_many_loaded_and_what_they_cost(
    capsys, monkeypatch, tmp_path
):
    """AC 2, AC 3 - the count beside the tools, and the skills' own share."""
    directory = tmp_path / "skills"
    write_skill(directory, "a", name="alpha", description="x" * 120)
    write_skill(directory, "b", name="beta", description="y" * 120)

    _, out = run_argv(capsys, monkeypatch, tmp_path, directory)

    assert "2 skills loaded" in out.out
    found = re.search(r"2 skills loaded, about (\d+) tokens per request", out.out)
    assert found, "the skills' own share was not reported"
    assert int(found.group(1)) > 0


def test_a_skill_that_could_not_load_is_named_at_startup_with_its_reason(
    capsys, monkeypatch, tmp_path
):
    """AC 4's startup half - proven at the loader, not until now at the line."""
    directory = tmp_path / "skills"
    write_skill(directory, "good", name="good", description="Fine")
    (directory / "broken").mkdir()

    _, out = run_argv(capsys, monkeypatch, tmp_path, directory)

    assert "skill not loaded - broken has no SKILL.md" in out.out
    assert "1 skill loaded" in out.out, "the good one should still have loaded"


def test_a_run_with_no_skills_says_nothing_about_them(capsys, monkeypatch, tmp_path):
    """AC 1 at the startup line - not "0 skills", which is a number and reads like one."""
    _, out = run_argv(capsys, monkeypatch, tmp_path, tmp_path / "none")

    assert "skill" not in out.out.lower()

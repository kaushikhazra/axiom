"""Instructions a user writes once and axiom follows when they apply.

A skill is a folder under `.axiom/skills/` holding a `SKILL.md`: markdown
instructions behind frontmatter carrying a name and a description.

**Only the name and the description are kept.** The instructions stay on disk
until a skill is actually invoked and are read from the file at that moment.
That is the whole economy of the feature - a catalogued skill costs its one
line on every request, and its instructions cost nothing until they are
wanted - and it is also what makes an edit during a run take effect without a
restart.

Problems are collected rather than raised, the way `config.read_servers` does
it: one unreadable skill costs that skill, not the session.
"""

from dataclasses import dataclass
from pathlib import Path

import frontmatter

# The one file a skill folder must have. Anything else beside it is the skill's
# own business - never loaded, and reachable by the model only if the
# instructions name it and it uses `read_file` (AC 25).
SKILL_FILE = "SKILL.md"

# Beside `.axiom/mcp.json` and `.axiom/model.json`, and resolved against the
# working directory rather than frozen anywhere.
DEFAULT_SKILLS_DIRECTORY = Path(".axiom") / "skills"

# What frontmatter has to carry. Everything else in it is ignored rather than
# refused, which is what lets a SKILL.md written for another agent load here
# unchanged (AC 24).
REQUIRED_FIELDS = ("name", "description")


@dataclass(frozen=True)
class Skill:
    """One skill, as the catalogue holds it.

    `path` rather than the instructions themselves, deliberately. Holding the
    text here would make it available to anything that can see a `Skill`, and
    the one rule this feature turns on is that instructions travel only when
    invoked.
    """

    name: str
    description: str
    path: Path

    def line(self) -> str:
        """The one line this skill costs on every request."""
        return f"- {self.name}: {self.description}"


@dataclass(frozen=True)
class Catalogue:
    """Every skill that loaded, and everything that did not.

    Empty is a perfectly good catalogue - it is what no directory, an empty
    directory and skills-switched-off all produce, and none of them is a
    failure.
    """

    skills: tuple[Skill, ...] = ()
    problems: tuple[str, ...] = ()

    def __len__(self) -> int:
        return len(self.skills)

    def find(self, name: str) -> Skill | None:
        return next((skill for skill in self.skills if skill.name == name), None)

    @property
    def names(self) -> tuple[str, ...]:
        return tuple(skill.name for skill in self.skills)


def read(directory: Path) -> Catalogue:
    """Every skill under `directory`, and a reason for each one that did not load.

    A missing directory and an empty one are the same answer, and neither is a
    problem: a project with no skills is the ordinary case, not a
    misconfiguration (AC 1, AC 30).
    """
    if not directory.is_dir():
        return Catalogue()

    loaded: list[Skill] = []
    problems: list[str] = []
    claimed: dict[str, str] = {}  # skill name -> the folder that got there first

    for folder in sorted(entry for entry in directory.iterdir() if entry.is_dir()):
        skill, problem = _one(folder)
        if problem is not None:
            problems.append(problem)
            continue
        first = claimed.get(skill.name)
        if first is not None:
            # Both folders are real and both say they are this skill. The one
            # that loaded is named rather than left to be guessed at, because
            # the user's next question is which of the two they just ran.
            problems.append(
                f"{folder.name} and {first} are both named {skill.name!r} - "
                f"using the one in {first}"
            )
            continue
        claimed[skill.name] = folder.name
        loaded.append(skill)

    return Catalogue(tuple(loaded), tuple(problems))


def fault_in(parsed) -> str | None:  # noqa: ANN001 - a frontmatter Post
    """Why this is not a usable skill, or None if it is one.

    One rule, used twice: the loader prefixes it with a folder name to report a
    skill that would not load, and `Library.write` returns it to a model that
    tried to create one. Written once deliberately - two sets of rules for what
    a valid skill is would drift, and the first sign of the drift would be a
    skill that writes without complaint and then refuses to load.

    The field is named rather than called malformed. "Malformed" sends someone
    back to read the whole file; "no description" sends them to one line of it.
    """
    missing = [
        field for field in REQUIRED_FIELDS if not str(parsed.get(field) or "").strip()
    ]
    if missing:
        return f"no {' and no '.join(missing)}"
    if not parsed.content.strip():
        # A description with nothing behind it. Offering it would put a promise
        # in the catalogue that invoking it cannot keep.
        return "no instructions"
    return None


def _one(folder: Path) -> tuple[Skill, None] | tuple[None, str]:
    """One folder as a skill, or the reason it is not one.

    Every return names the folder, because a bare "missing description" on a
    startup line tells the user nothing about which of their skills to go and
    fix.
    """
    path = folder / SKILL_FILE
    if not path.is_file():
        return None, f"{folder.name} has no {SKILL_FILE}"

    try:
        # `frontmatter` wants text, and the same `utf-8-sig` reasoning as
        # `config.read_servers` applies: this is a file a user writes by hand,
        # and on Windows the ordinary way to write one leaves a byte order
        # mark. The decoder removes it before the YAML parser ever sees it.
        parsed = frontmatter.loads(path.read_text(encoding="utf-8-sig"))
    except OSError as unreadable:
        reason = unreadable.strerror or unreadable
        return None, f"{folder.name} could not be read ({reason})"
    except Exception as unparsable:  # noqa: BLE001 - any YAML failure, named
        return (
            None,
            f"{folder.name} has frontmatter that could not be read ({unparsable})",
        )

    fault = fault_in(parsed)
    if fault is not None:
        return None, f"{folder.name} has {fault}"

    return (
        Skill(
            name=str(parsed["name"]).strip(),
            description=str(parsed["description"]).strip(),
            path=path,
        ),
        None,
    )


def instructions(skill: Skill) -> str:
    """A skill's instructions, read from disk now rather than at startup.

    Read at the moment of use, which is what AC 33 asks for and what makes an
    edit during a run take effect. It also means the file may be gone by the
    time it is wanted, and a missing file has to say so rather than hand back
    something stale - there is nothing stale to hand back, which is the point.

    Returns the same `error:` shape every other failure in axiom uses, so a
    caller does not need a second way to notice.
    """
    try:
        parsed = frontmatter.loads(skill.path.read_text(encoding="utf-8-sig"))
    except OSError:
        return (
            f"error: {skill.name} is no longer readable at {skill.path} - "
            f"it may have been moved or deleted since axiom started"
        )
    except Exception as unparsable:  # noqa: BLE001
        return f"error: {skill.name} could not be read ({unparsable})"

    body = parsed.content.strip()
    if not body:
        return f"error: {skill.name} has no instructions"
    return body


class Library:
    """The session's skills: where they live, what loaded, and how that changes.

    A class rather than a `Catalogue` passed around, for one reason: AC 18 and
    AC 20 promise that a skill written or deleted mid-session is listed and
    invocable straight away. That needs somewhere for the new catalogue to
    *land*, and a frozen dataclass handed to a tool has nowhere.

    This is the twin of `schedule.Schedule` and is injected into tools the same
    way, through a flag on `Tool` - because it is the session's, not the
    model's, and `tools.run` refuses any argument a tool did not declare.
    """

    def __init__(self, directory: Path) -> None:
        self.directory = directory
        self.catalogue = read(directory)

    def refresh(self) -> None:
        self.catalogue = read(self.directory)

    def folder(self, name: str) -> Path:
        """Where a skill by this name lives, whether or not it exists yet."""
        found = self.catalogue.find(name)
        return found.path.parent if found else self.directory / name

    # -- what the four tools do -------------------------------------------

    def source(self, name: str) -> str:
        """A skill exactly as it is written, frontmatter included (AC 17).

        Deliberately not `instructions()`. That returns the body, which is what
        a model follows; this returns the file, which is what a model edits.
        """
        found = self.catalogue.find(name)
        if found is None:
            return self._no_such(name)
        try:
            return found.path.read_text(encoding="utf-8-sig")
        except OSError:
            return f"error: {name} is no longer readable at {found.path}"

    def write(self, name: str, content: str) -> str:
        """Create or replace a skill, refusing anything that would not load.

        **Validated before anything is opened for writing.** That is AC 42 by
        construction rather than by care: there is no path here where a refused
        write has already truncated a good skill, because the refusal happens
        before the file is touched at all.
        """
        try:
            parsed = frontmatter.loads(content)
        except Exception as unparsable:  # noqa: BLE001
            return f"error: not written - frontmatter could not be read ({unparsable})"

        fault = fault_in(parsed)
        if fault is not None:
            return f"error: not written - it has {fault}"

        target = self.folder(name) / SKILL_FILE
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        # Before returning, so the very next thing the model is told already
        # reflects the write. AC 18 and AC 19.
        self.refresh()
        return f"wrote skill {name} to {target}"

    def delete(self, name: str) -> str:
        found = self.catalogue.find(name)
        if found is None:
            return self._no_such(name)
        try:
            found.path.unlink()
            # The folder too, when this leaves it empty - otherwise a deleted
            # skill leaves a directory that the loader reports as "has no
            # SKILL.md" on every later run, which is a complaint about a skill
            # the user already removed.
            if not any(found.path.parent.iterdir()):
                found.path.parent.rmdir()
        except OSError as failed:
            return f"error: could not delete {name} ({failed.strerror or failed})"
        self.refresh()
        return f"deleted skill {name}"

    def invoke(self, name: str) -> str:
        found = self.catalogue.find(name)
        if found is None:
            return self._no_such(name)
        return instructions(found)

    def _no_such(self, name: str) -> str:
        """Named, with what there is instead.

        The alternatives are listed because a model that got the name slightly
        wrong can correct itself from this, and one that is told only "no such
        skill" will answer from memory instead.
        """
        available = ", ".join(self.catalogue.names) or "none"
        return f"error: there is no skill named {name!r} - available: {available}"


def catalogue_text(catalogue: Catalogue) -> str:
    """The skills as the model is told about them: one line each, no instructions.

    This string is the entire cost of having skills. If a skill's instructions
    ever appear in what this returns, the feature has become a way to make every
    request more expensive rather than a way to make one request cheaper - so
    the test that guards it asserts on what is *sent*, not on this function.

    **The preamble is provisional and its wording is an open question.** It was
    302 characters and is now 149, which is about 38 tokens off every request -
    measured, because at one skill the old paragraph cost more than three times
    the skill it introduced. But this text is also the only lever on AC 15,
    where a model has to reach for a skill instead of answering from memory, and
    the cheapest prompt is not automatically the one that gets that right. Do
    not shorten it further on taste. Measure it.
    """
    if not catalogue.skills:
        return ""
    return "\n".join(
        [
            "",
            "Skills you can invoke. Each is instructions someone wrote for one "
            "kind of work. When one fits, invoke it and follow it rather than "
            "working from memory.",
            "",
            *(skill.line() for skill in catalogue.skills),
        ]
    )

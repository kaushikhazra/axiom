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

    missing = [
        field for field in REQUIRED_FIELDS if not str(parsed.get(field) or "").strip()
    ]
    if missing:
        # The field is named. "malformed" sends the user back to read the whole
        # file; "no description" sends them to one line of it.
        return None, f"{folder.name} has no {' and no '.join(missing)}"

    if not parsed.content.strip():
        # A description with nothing behind it. Offering it would put a promise
        # in the catalogue that invoking it cannot keep.
        return None, f"{folder.name} has no instructions"

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

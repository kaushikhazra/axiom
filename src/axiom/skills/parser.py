"""
SKILL.md parsing and validation against the agentskills.io frontmatter
rules (agentskills.io/specification, fetched 2026-07-26 -- see
requirement.md SK-2 for the verbatim rule list).
"""

from __future__ import annotations

import re
from pathlib import Path

from axiom.skills.port import SkillContent

_FRONTMATTER_RE = re.compile(r"\A---\n(.*?)\n---\n(.*)\Z", re.DOTALL)
_NAME_RE = re.compile(
    r"^[a-z0-9]+(-[a-z0-9]+)*$"
)  # no leading/trailing/consecutive hyphens


class SkillValidationError(Exception):
    """Raised by parse_skill_md() on any frontmatter/format violation.
    Caught exclusively by SkillsRegistry -- never propagates to loop.py."""


def _parse_frontmatter_block(block: str) -> dict:
    """Minimal line-based key: value parser (design.md D8) -- sufficient
    for the flat 5-key frontmatter agentskills.io defines. Only 'metadata'
    nests; nested keys are collected as a flat dict under 'metadata' by
    indentation.

    A bare 'metadata:' header (empty value) is special-cased to initialize
    result["metadata"] = {} directly. Without this, the generic branch
    below would first set result["metadata"] = "" (a string), and the
    nested-line branch's dict assignment would crash on the very next
    indented line -- exactly the shape of the agentskills.io spec's own
    documented example ("metadata:\\n  author: ...\\n  version: ...").

    A bare '|' or '>' value (YAML block-scalar indicator) is rejected with
    SkillValidationError rather than silently mis-parsed -- this parser
    does not fold multi-line scalars.
    """
    result: dict = {}
    current_key: str | None = None
    for line in block.splitlines():
        if not line.strip():
            continue
        if line.startswith(("  ", "\t")) and current_key == "metadata":
            k, _, v = line.strip().partition(":")
            result["metadata"][k.strip()] = v.strip().strip('"')
            continue
        k, sep, v = line.partition(":")
        if not sep:
            continue
        key = k.strip()
        value = v.strip()
        if value in ("|", ">"):
            raise SkillValidationError(
                f"unsupported multi-line YAML scalar for {key!r} "
                "(block-scalar syntax is not supported by this parser)"
            )
        if key == "metadata" and not value:
            current_key = "metadata"
            result["metadata"] = {}
            continue
        current_key = key
        result[current_key] = value.strip('"')
    return result


def parse_skill_md(path: Path) -> SkillContent:
    """Parse and validate one SKILL.md. path is the file itself
    ({skills_dir}/{name}/SKILL.md); the skill name is derived from the
    PARENT directory name, then cross-checked against frontmatter 'name'
    (spec rule: name must match the parent directory name)."""
    dir_name = path.parent.name
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        # A permission error, any other OS-level read failure, OR a
        # non-UTF-8 file must become a SkillValidationError (caught and
        # excluded by the registry) -- never an uncaught exception
        # propagating out of discovery. UnicodeDecodeError is a ValueError
        # subclass, NOT an OSError subclass -- both must be caught.
        raise SkillValidationError(f"{path}: failed to read: {exc}") from exc

    m = _FRONTMATTER_RE.match(text)
    if not m:
        raise SkillValidationError(f"{path}: missing or malformed frontmatter block")

    frontmatter = _parse_frontmatter_block(m.group(1))
    body = m.group(2)

    name = frontmatter.get("name", "")
    description = frontmatter.get("description", "")

    if not name:
        raise SkillValidationError(f"{path}: 'name' is required")
    if len(name) > 64 or not _NAME_RE.match(name):
        raise SkillValidationError(
            f"{path}: 'name' {name!r} must be 1-64 chars, lowercase "
            "alphanumeric + hyphens, no leading/trailing/consecutive hyphens"
        )
    if name != dir_name:
        raise SkillValidationError(
            f"{path}: 'name' {name!r} must match parent directory name {dir_name!r}"
        )
    if not description:
        raise SkillValidationError(f"{path}: 'description' is required")
    if len(description) > 1024:
        raise SkillValidationError(f"{path}: 'description' exceeds 1024 chars")

    return SkillContent(
        name=name, description=description, body=body, frontmatter=frontmatter
    )

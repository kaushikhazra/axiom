"""
SkillsRegistry -- the concrete SkillsPort. Owns skills_dir; discovers,
validates, and serves skills from {skills_dir}/*/SKILL.md.
"""

from __future__ import annotations

import logging
from pathlib import Path

from axiom.skills.parser import SkillValidationError, parse_skill_md
from axiom.skills.port import SkillContent, SkillNotFoundError, SkillSpec

logger = logging.getLogger("axiom.skills")


class SkillsRegistry:
    def __init__(self, skills_dir: Path) -> None:
        self._skills_dir = skills_dir

    def _discover(self) -> dict[str, SkillContent]:
        """Re-scan skills_dir on every call (design.md D3 -- no caching, so
        a skill authored mid-run is picked up on the very next call).
        skills_dir not existing is a valid, common state (SK-6) -- empty
        result, not an error.

        iterdir() itself can raise OSError (e.g. permission-denied on
        skills_dir) -- guarded the same way a malformed individual
        SKILL.md is: logged and degraded to an empty scan, not propagated.
        """
        found: dict[str, SkillContent] = {}
        if not self._skills_dir.is_dir():
            return found
        try:
            entries = sorted(self._skills_dir.iterdir())
        except OSError as exc:
            logger.debug("[SKILLS_DIR_UNREADABLE] %s", exc)
            return found
        for entry in entries:
            skill_md = entry / "SKILL.md"
            if not entry.is_dir() or not skill_md.is_file():
                continue
            try:
                content = parse_skill_md(skill_md)
            except SkillValidationError as exc:
                logger.debug("[SKILL_INVALID] %s", exc)
                continue
            found[content.name] = content
        return found

    def list_skills(self) -> list[SkillSpec]:
        return [
            SkillSpec(name=c.name, description=c.description)
            for c in self._discover().values()
        ]

    def get_skill(self, name: str) -> SkillContent:
        found = self._discover()
        if name not in found:
            raise SkillNotFoundError(f"no such skill: {name!r}")
        return found[name]

    def search(self, query: str) -> list[SkillSpec]:
        q = query.lower()
        return [
            SkillSpec(name=c.name, description=c.description)
            for c in self._discover().values()
            if q in c.name.lower() or q in c.description.lower()
        ]

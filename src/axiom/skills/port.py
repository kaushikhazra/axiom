"""
Skills port contract -- the loop-level seam for Axiom's self-authored,
progressively-disclosed capabilities.

Unlike ToolsPort (adapter-side, axiom.tools), SkillsPort is consumed
directly by loop.py and interfaces.py -- the same relationship MemoryPort
already has with the core loop (architecture.md places Skills alongside
Memory in the 6-port list, not alongside Tools).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True)
class SkillSpec:
    """Discovery-level payload -- name + description only (agentskills.io
    'discovery' stage). No body, no bundled-file contents."""

    name: str
    description: str


@dataclass(frozen=True)
class SkillContent:
    """Activation-level payload -- the full parsed SKILL.md."""

    name: str
    description: str
    body: str  # Markdown content after the frontmatter block
    frontmatter: dict = field(
        default_factory=dict
    )  # optional fields, unenforced (license/compatibility/metadata/allowed-tools)


class SkillNotFoundError(Exception):
    """Raised by get_skill() when skill_name is not in the current catalog.
    Caught by loop.py -- never propagates past the loop (design.md D5)."""


class SkillsPort(Protocol):
    def list_skills(self) -> list[SkillSpec]:
        """Discovery-level catalog of every valid skill. Never raises --
        a malformed skill is excluded and logged, not an error (SK-2)."""
        ...

    def get_skill(self, name: str) -> SkillContent:
        """Full content of one skill. Raises SkillNotFoundError if name
        is not present (or is present but invalid -- same exclusion as
        list_skills(), SK-2)."""
        ...

    def search(self, query: str) -> list[SkillSpec]:
        """Discovery-level results relevant to query (name/description
        keyword match). Not wired into loop.py's catalog assembly in M5
        (design.md D9) -- a capability for future callers."""
        ...

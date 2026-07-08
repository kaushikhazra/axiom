"""
Persona package — loads the static persona string from persona.txt.

Uses stdlib only (pathlib). No mutation, no persistence.
Loaded once at composition time by agent.py; passed into ClaudeAdapter.__init__().
"""

from __future__ import annotations

from pathlib import Path

_PERSONA_FILE = Path(__file__).parent / "persona.txt"


def load() -> str:
    """Load and return the static persona string from persona.txt.

    Raises:
        FileNotFoundError: If persona.txt is missing from the package directory.
        ValueError: If persona.txt exists but is empty.
    """
    if not _PERSONA_FILE.exists():
        raise FileNotFoundError(
            f"Persona file not found: {_PERSONA_FILE}. "
            "Create src/axiom/persona/persona.txt to define the agent persona."
        )
    content = _PERSONA_FILE.read_text(encoding="utf-8").strip()
    if not content:
        raise ValueError(
            f"Persona file is empty: {_PERSONA_FILE}. "
            "Add persona content to src/axiom/persona/persona.txt."
        )
    return content

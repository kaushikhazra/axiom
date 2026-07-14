"""Type classification and importance scoring — pure functions."""

from __future__ import annotations
import re

_PROCEDURAL_KEYWORDS = {
    "how to",
    "steps",
    "workflow",
    "process",
    "procedure",
    "guide",
    "instructions",
    "method",
    "tutorial",
    "recipe",
}
_IDENTITY_KEYWORDS = {
    "i am",
    "my name",
    "i believe",
    "i think",
    "i prefer",
    "i like",
    "i am called",
    "velasari",
    "my identity",
    "i feel",
}
_SEMANTIC_KEYWORDS = {
    "is defined as",
    "means",
    "refers to",
    "is a type of",
    "definition",
    "fact:",
    "note:",
    "the answer is",
    "according to",
}
_PERSON_PATTERNS = [
    re.compile(r"\bperson:\s*\w+", re.IGNORECASE),
    re.compile(
        r"\b(user|kaushik|client|colleague|friend|boss|manager)\b", re.IGNORECASE
    ),
    re.compile(r"\bname[sd]?\s+(is|are)\s+\w+", re.IGNORECASE),
]
_RELATIONAL_KEYWORDS = {
    "because",
    "therefore",
    "causes",
    "leads to",
    "results in",
    "consequently",
    "hence",
    "thus",
    "since",
    "so that",
}


def classify_type(content: str) -> tuple[str, float]:
    """Return (memory_type, confidence). Confidence capped at 0.8; below 0.2 -> episodic."""
    lower = content.lower()

    # Identity check
    id_matches = sum(1 for kw in _IDENTITY_KEYWORDS if kw in lower)
    if id_matches >= 2:
        return ("identity", min(0.4 + id_matches * 0.1, 0.8))

    # Person check
    person_matches = sum(1 for p in _PERSON_PATTERNS if p.search(content))
    if person_matches >= 1:
        return ("person", min(0.4 + person_matches * 0.2, 0.8))

    # Procedural check
    proc_matches = sum(1 for kw in _PROCEDURAL_KEYWORDS if kw in lower)
    if proc_matches >= 2:
        return ("procedural", min(0.4 + proc_matches * 0.1, 0.8))

    # Semantic check
    sem_matches = sum(1 for kw in _SEMANTIC_KEYWORDS if kw in lower)
    if sem_matches >= 1:
        return ("semantic", min(0.4 + sem_matches * 0.1, 0.8))

    # Identity (single keyword high-confidence words)
    if any(kw in lower for kw in ("my name is", "i am velasari", "my identity")):
        return ("identity", 0.7)

    # Default
    return ("episodic", 0.15)  # below 0.2 -> episodic default


def score_importance(
    content: str, memory_type: str, caller_override: float | None = None
) -> float:
    """Score importance [0.0, 1.0]. Caller override always wins."""
    if caller_override is not None:
        return max(0.0, min(1.0, caller_override))

    score = 0.5  # base

    # Type bonuses/penalties
    if memory_type == "identity":
        score += 0.2
    elif memory_type == "person":
        score += 0.15
    elif memory_type == "working":
        score -= 0.1

    # Named entity heuristic (capitalized words not at sentence start)
    words = content.split()
    cap_words = sum(
        1 for i, w in enumerate(words) if i > 0 and w and w[0].isupper() and w.isalpha()
    )
    if cap_words >= 1:
        score += 0.1

    # Relational keywords
    lower = content.lower()
    if any(kw in lower for kw in _RELATIONAL_KEYWORDS):
        score += 0.1

    # Length bonus
    if len(content) > 200:
        score += 0.1

    return max(0.0, min(1.0, score))

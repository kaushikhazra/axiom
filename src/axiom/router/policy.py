"""
RoutePolicy -- the declarative, pattern-based routing rules RT-4/RT-5/RT-6
evaluate. Deliberately NOT an NLP classifier (requirement.md Purpose) --
every field here is a plain glob/regex/length rule, kept together so the
precedence order (privacy > capability > cost/volume default) has exactly
one place to be evaluated and exactly one place to be tested.
"""

from __future__ import annotations

import fnmatch
import re
from dataclasses import dataclass, field


@dataclass(frozen=True)
class RoutePolicy:
    privacy_patterns: list[str] = field(default_factory=list)  # RT-4
    bulk_threshold_chars: int = 200  # RT-5
    capability_patterns: list[str] = field(default_factory=list)  # RT-6


def _matches_any(instruction: str, patterns: list[str]) -> bool:
    """glob-style match (fnmatch) OR regex match, tried in that order per
    pattern -- lets simple patterns stay simple (e.g. '*.env', '*/secrets/*')
    while still allowing a regex when a caller needs one (e.g. 'password|token')."""
    for pattern in patterns:
        if fnmatch.fnmatch(instruction, pattern):
            return True
        try:
            if re.search(pattern, instruction):
                return True
        except re.error:
            continue  # not a valid regex -- fnmatch already tried; skip silently
    return False


class RoutingDecision:
    PRIVACY = "privacy"
    CAPABILITY = "capability"
    BULK_DEFAULT = "bulk_default"
    CONDUCTOR_DEFAULT = "conductor_default"


def evaluate(instruction: str, policy: RoutePolicy) -> tuple[str, str]:
    """Returns (provider_name, decision_reason). provider_name is "local" or
    "claude" (or the "__conductor__" sentinel the caller resolves against the
    Conductor's own provider for CONDUCTOR_DEFAULT -- see Router.select_worker).

    Precedence: privacy (RT-4) > capability (RT-6) > bulk default (RT-5) >
    Conductor-provider fallthrough.
    """
    if _matches_any(instruction, policy.privacy_patterns):
        return "local", RoutingDecision.PRIVACY
    if _matches_any(instruction, policy.capability_patterns):
        return "claude", RoutingDecision.CAPABILITY
    if len(instruction) <= policy.bulk_threshold_chars:
        return "local", RoutingDecision.BULK_DEFAULT
    return "__conductor__", RoutingDecision.CONDUCTOR_DEFAULT

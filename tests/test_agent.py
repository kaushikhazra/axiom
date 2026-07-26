"""
Unit tests for axiom.agent.Agent's constructor-level validation.

M6 / dryrun-code-1 W1: restores the input validation the pre-M6 if/elif
provider-selection block used to provide. Kept minimal (validation-only) --
Agent's full composition (memory adapter, Router, PraoLoop) is exercised
via the e2e test suite and axiom-cli live verification instead of unit
tests here, since constructing a real Agent pulls in the full memory/
embedding stack.
"""

from __future__ import annotations

import pytest

from axiom.agent import Agent


class TestProviderValidation:
    def test_invalid_provider_raises_value_error_immediately(self) -> None:
        """The check must fire before any expensive setup (persona load,
        memory adapter construction) -- confirmed by the fact this test
        doesn't require memory infra to be mocked/available."""
        with pytest.raises(ValueError, match="unknown provider"):
            Agent(provider="bogus")

    def test_empty_string_provider_raises_value_error(self) -> None:
        """Boundary case: an empty string is not None and not a valid
        choice -- must be rejected the same as any other invalid value."""
        with pytest.raises(ValueError, match="unknown provider"):
            Agent(provider="")

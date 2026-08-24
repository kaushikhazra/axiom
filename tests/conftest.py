"""Shared test isolation.

AXIOM_DEBUG_MAX_CONTEXT is a debugging override that live compaction runs
export into the shell and leave there. Six tests read the effective context
out of the startup line, so an ambient value silently rewrites what they are
asserting against - the suite went red on a machine where nothing was wrong
with the code.

No test should inherit it. The ones that are actually about the override set
it themselves, which still works: this clears it before the test body runs.
"""

import pytest


@pytest.fixture(autouse=True)
def isolate_debug_context(monkeypatch):
    monkeypatch.delenv("AXIOM_DEBUG_MAX_CONTEXT", raising=False)

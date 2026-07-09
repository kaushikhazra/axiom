"""
Live end-to-end tests for the local adapter (LocalAdapter + PraoLoop via Agent).

Requires:
  - litellm installed (real package, not the mock injected by test_local_adapter.py)
  - Ollama running at http://localhost:11434 with qwen2.5:7b pulled

Marked @pytest.mark.e2e_local.  All tests carry skipif conditions for both
prerequisites so they are COLLECTED on every run (visible to --collect-only and
marker queries) but SKIPPED when prerequisites are absent — no failure, no error.

Invoke explicitly with:
    pytest -m e2e_local -v tests/test_local_e2e.py
"""

from __future__ import annotations

import importlib.metadata
import socket

import httpx
import pytest

from axiom.agent import Agent

# ---------------------------------------------------------------------------
# Prerequisite checks — evaluated once at module load (collection) time.
# ---------------------------------------------------------------------------


# Check 1: litellm actually installed on disk?
# We use importlib.metadata (not `import litellm`) because test_local_adapter.py
# injects a MagicMock into sys.modules["litellm"] at collection time.  A bare
# `import litellm` would resolve to that mock, masking the fact that the real
# package is absent and causing live tests to fail with cryptic errors instead
# of skipping cleanly.  importlib.metadata queries package metadata files on
# disk and is not fooled by sys.modules.
def _litellm_installed() -> bool:
    try:
        importlib.metadata.version("litellm")
        return True
    except importlib.metadata.PackageNotFoundError:
        return False


# Check 2: Ollama reachable at http://localhost:11434 ?
_OLLAMA_HOST = "localhost"
_OLLAMA_PORT = 11434
_OLLAMA_BASE = f"http://{_OLLAMA_HOST}:{_OLLAMA_PORT}"


def _ollama_reachable() -> bool:
    try:
        sock = socket.create_connection((_OLLAMA_HOST, _OLLAMA_PORT), timeout=2)
        sock.close()
        return True
    except OSError:
        return False


_SKIP_NO_LITELLM = pytest.mark.skipif(
    not _litellm_installed(),
    reason="litellm is not installed — run 'pip install litellm' to enable e2e_local tests",
)
_SKIP_NO_OLLAMA = pytest.mark.skipif(
    not _ollama_reachable(),
    reason=f"Ollama is not reachable at {_OLLAMA_BASE} — start Ollama to enable e2e_local tests",
)

# Apply both skip conditions + the e2e_local marker to every test in this module.
pytestmark = [pytest.mark.e2e_local, _SKIP_NO_LITELLM, _SKIP_NO_OLLAMA]

# ---------------------------------------------------------------------------
# Module-scoped pre-warm fixture
# ---------------------------------------------------------------------------

_MODEL_NAME = "qwen2.5:7b"


@pytest.fixture(scope="module", autouse=True)
def prewarm_ollama() -> None:
    """Pre-warm the model so timing-sensitive tests don't measure cold-load time.

    Sends a trivial generate request to Ollama directly (not via the Agent) with
    a generous timeout to cover first-load from disk.  Subsequent calls are warm-fast.

    Per design §8 (Performance & Cold Start / pre-warming note).
    Best-effort: if pre-warm fails the tests may be slow but will not be broken.
    """
    try:
        httpx.post(
            f"{_OLLAMA_BASE}/api/generate",
            json={"model": _MODEL_NAME, "prompt": "hi", "stream": False},
            timeout=120.0,  # generous: first load from disk can take 10-30s on GPU
        )
    except Exception:
        pass


# ---------------------------------------------------------------------------
# E2E tests
# ---------------------------------------------------------------------------


def test_trivial_respond_shortcircuit() -> None:
    """A simple greeting should produce a RESPOND-path result without tool use.

    Acceptance criteria (MLA-5 / §11.4 row 1):
    - Agent.run() returns a non-empty string.
    - No AdapterError or uncaught exception.
    - The response must be readable natural-language text (not an error sentinel).
    """
    agent = Agent(provider="local")
    response = agent.run("Hello! How are you today?")

    assert isinstance(response, str), "response must be a str"
    assert response.strip(), "response must not be empty / whitespace-only"
    # Must not be an error path
    assert not response.startswith("[Error:"), (
        f"Agent returned an error-path response: {response!r}"
    )
    # Must not be a bare fallback sentinel (model completely failed to parse intent)
    assert "[FALLBACK_RESPOND]" not in response or len(response) > len(
        "[FALLBACK_RESPOND]"
    ), "Response appears to be an unparsed fallback — model may have returned no text"


def test_reason_act_observe_cycle_shell_tool() -> None:
    """A task requiring shell tool use should complete the full PRAO cycle.

    Acceptance criteria (MLA-5 / §11.4 row 2):
    - Agent.run() returns a non-empty string.
    - The response reflects real directory/file output — must mention at least one
      recognisable file-system element (e.g. 'src', 'tests', 'pyproject') that
      lives in the Axiom project root, confirming the shell tool actually ran.
    - No AdapterError or uncaught exception.

    Prompt instructs the model to list files in the current directory, which maps
    directly to the shell tool (run_shell_command with e.g. 'ls' or 'dir').
    """
    agent = Agent(provider="local")
    response = agent.run(
        "List the files and directories in the current working directory "
        "using the shell tool, then tell me what you see."
    )

    assert isinstance(response, str), "response must be a str"
    assert response.strip(), "response must not be empty / whitespace-only"
    assert not response.startswith("[Error:"), (
        f"Agent returned an error-path response: {response!r}"
    )

    # The shell tool should have returned directory contents that include at least
    # one of these well-known Axiom project artefacts.  Robust to case differences.
    response_lower = response.lower()
    known_artefacts = ["src", "tests", "pyproject", "readme", ".claude"]
    assert any(artefact in response_lower for artefact in known_artefacts), (
        f"Response does not mention any expected project artefact "
        f"({known_artefacts}) — shell tool may not have executed.\n"
        f"Response was: {response!r}"
    )

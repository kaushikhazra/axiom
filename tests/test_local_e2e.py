"""
Live end-to-end tests for the local adapter (LocalAdapter + PraoLoop via Agent).

Uses smolagents CodeAgent + Ollama qwen2.5:7b.

Requires:
  - smolagents installed
  - Ollama running at http://localhost:11434 with qwen2.5:7b pulled

Marked @pytest.mark.e2e_local.  All tests carry skipif conditions for both
prerequisites so they are COLLECTED on every run (visible to --collect-only and
marker queries) but SKIPPED when prerequisites are absent — no failure, no error.

Invoke explicitly with:
    pytest -m e2e_local -v -s tests/test_local_e2e.py
"""

from __future__ import annotations

import importlib.metadata
import os
import socket
import time

import httpx
import pytest

from axiom import persona as persona_pkg
from axiom.agent import Agent
from axiom.loop import PraoLoop
from axiom.observability import timing
from axiom.providers.local_adapter import LocalAdapter

# ---------------------------------------------------------------------------
# Prerequisite checks — evaluated once at module load (collection) time.
# ---------------------------------------------------------------------------


def _smolagents_installed() -> bool:
    try:
        importlib.metadata.version("smolagents")
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


_SKIP_NO_SMOLAGENTS = pytest.mark.skipif(
    not _smolagents_installed(),
    reason="smolagents is not installed — run 'pip install smolagents' to enable e2e_local tests",
)
_SKIP_NO_OLLAMA = pytest.mark.skipif(
    not _ollama_reachable(),
    reason=f"Ollama is not reachable at {_OLLAMA_BASE} — start Ollama to enable e2e_local tests",
)

# Apply both skip conditions + the e2e_local marker to every test in this module.
pytestmark = [pytest.mark.e2e_local, _SKIP_NO_SMOLAGENTS, _SKIP_NO_OLLAMA]

# ---------------------------------------------------------------------------
# Module-scoped pre-warm fixture
# ---------------------------------------------------------------------------

_MODEL_NAME = "qwen2.5:7b"


@pytest.fixture(scope="module", autouse=True)
def prewarm_ollama() -> None:
    """Pre-warm the model so timing-sensitive tests don't measure cold-load time.

    Sends a trivial generate request to Ollama directly (not via the Agent) with
    a generous timeout to cover first-load from disk.  Subsequent calls are warm-fast.

    Per design SS8 (Latency Note / pre-warming).
    Best-effort: if pre-warm fails the tests may be slow but will not be broken.
    """
    try:
        httpx.post(
            f"{_OLLAMA_BASE}/api/generate",
            json={"model": _MODEL_NAME, "prompt": "hi", "stream": False},
            timeout=120.0,  # generous: first load from disk can take 10-30s on GPU
        )
        print(f"\n[prewarm] model {_MODEL_NAME} pre-warmed successfully.")
    except Exception as exc:
        print(f"\n[prewarm] pre-warm failed (tests may be slow): {exc}")


# ---------------------------------------------------------------------------
# E2E Scenario 1: hello — RESPOND path, no tool use
# ---------------------------------------------------------------------------


def test_e2e_hello_respond_path() -> None:
    """E2E #1 — 'hello' input: expect RESPOND path, a coherent greeting, NO tool use.

    Acceptance criteria (MLA-5 / design SS12.4 row 1):
    - Agent.run() returns a non-empty string.
    - No AdapterError or uncaught exception.
    - Response is readable natural-language text (not an error sentinel).
    - Response does not start with '[Error:' (error path).
    - Response does not consist solely of a '[FALLBACK_RESPOND]' sentinel.
    """
    agent = Agent(provider="local", debug=True)

    t0 = time.monotonic()
    response = agent.run("hello")
    latency_s = time.monotonic() - t0

    print(f"\n[E2E #1 hello] latency={latency_s:.1f}s")
    print(f"[E2E #1 hello] response={response!r}")

    assert isinstance(response, str), "response must be a str"
    assert response.strip(), "response must not be empty / whitespace-only"
    assert not response.startswith("[Error:"), (
        f"Agent returned an error-path response: {response!r}"
    )
    assert not (response.startswith("[FALLBACK_RESPOND]") and len(response) < 30), (
        "Response appears to be a bare fallback sentinel — model failed to produce text"
    )


# ---------------------------------------------------------------------------
# E2E Scenario 2: weather Durgapur — DuckDuckGoSearchTool
# ---------------------------------------------------------------------------


def test_e2e_weather_durgapur() -> None:
    """E2E #2 — weather search: expect CodeAgent to use DuckDuckGoSearchTool.

    Acceptance criteria (MLA-5 / design SS12.4 row 2):
    - Agent.run() returns a non-empty string.
    - No AdapterError or uncaught exception.
    - Response references Durgapur or West Bengal or contains weather-related
      content (temperature, weather, forecast, humid, etc.).
    - The CodeAgent must have used DuckDuckGoSearchTool (inferred from response content).

    Note (OQ-4 — DuckDuckGo rate limits): DuckDuckGo may be rate-limited or return
    no results. The assertion is on response content presence, not specific content.
    A response mentioning 'search' or 'could not' is also acceptable if the agent
    attempted the search even under rate-limiting.
    """
    agent = Agent(provider="local", debug=True)

    t0 = time.monotonic()
    response = agent.run("What is the current weather in Durgapur, West Bengal, India?")
    latency_s = time.monotonic() - t0

    print(f"\n[E2E #2 weather] latency={latency_s:.1f}s")
    print(f"[E2E #2 weather] response={response!r}")

    assert isinstance(response, str), "response must be a str"
    assert response.strip(), "response must not be empty / whitespace-only"
    assert not response.startswith("[Error:"), (
        f"Agent returned an error-path response: {response!r}"
    )

    # Response must contain weather-related or search-attempt content.
    response_lower = response.lower()
    weather_signals = [
        "durgapur",
        "west bengal",
        "weather",
        "temperature",
        "forecast",
        "humid",
        "rain",
        "celsius",
        "°c",
        "search",
        "could not",
        "unable",
        "found",
    ]
    assert any(sig in response_lower for sig in weather_signals), (
        f"Response does not mention any weather/search signals {weather_signals}.\n"
        f"Response was: {response!r}"
    )


# ---------------------------------------------------------------------------
# E2E Scenario 3: create + run python file
# ---------------------------------------------------------------------------


def test_e2e_create_and_run_python_file() -> None:
    """E2E #3 — literal requirement: create a python file, execute it, show output.

    Literal input: 'Create a python file in the current folder, which will print
    hello, execute it, and show the output.'

    Acceptance criteria (MLA-5 / design SS12.4 row 3 / W3 resolution):
    - Agent.run() returns a non-empty string.
    - No AdapterError or uncaught exception.
    - Response contains 'hello' (case-insensitive) — confirming file was executed.
    - A .py file exists on disk in the current working directory after the run
      (confirming real file creation, not just in-memory execution).

    M4 update: the CodeAgent's generated code can no longer call bare open()
    or subprocess directly -- 'subprocess' was removed from
    additional_authorized_imports and open() is no longer pre-injected
    (design.md AC-04.4/AC-05.4). This scenario now depends on the model
    choosing to call the gated WriteFileTool/RunShellTool instead (both
    auto-approved for this test via gate=GuardrailsGate(auto_approve=True)).
    Both tools are advertised to the model via smolagents' own tool-listing
    in the system prompt, the same way DuckDuckGoSearchTool already is.

    Note: wired directly via LocalAdapter + PraoLoop (not via Agent convenience
    class) to allow max_steps=8. qwen2.5:7b typically needs 4-6 steps for this
    task; the default max_steps=5 is too tight for the write+execute+report flow.
    """
    from pathlib import Path

    from axiom.tools.guardrails import GuardrailsGate

    persona_text = persona_pkg.load()
    # M4: gate=auto_approve=True -- this test's entire point is verifying a
    # real write+execute happens, so it must auto-approve the DESTRUCTIVE
    # write_file/run_shell calls rather than hang/deny on non-interactive
    # stdin (design.md D11).
    adapter = LocalAdapter(
        persona=persona_text,
        working_dir=Path(os.getcwd()),
        gate=GuardrailsGate(auto_approve=True),
        max_steps=8,
    )
    loop = PraoLoop(
        perceive=adapter,
        reason=adapter,
        act=adapter,
        observe=adapter,
        max_cycles=10,
    )

    # Test-isolation: remove any stale hello*.py artifacts left by prior runs so
    # the pre-scan baseline starts clean and the new-file delta is accurate.
    cwd = os.getcwd()
    _STALE_PATTERNS = ("hello.py", "hello_world.py", "hello_python.py")
    for _fname in _STALE_PATTERNS:
        _fpath = os.path.join(cwd, _fname)
        if os.path.exists(_fpath):
            os.remove(_fpath)
            print(f"\n[E2E #3 create+run] removed stale artifact: {_fpath}")

    # Record .py files before to detect newly created ones.
    py_files_before = set(f for f in os.listdir(cwd) if f.endswith(".py"))

    t0 = time.monotonic()
    response, _run_state = timing.timed_run(
        loop.run,
        "Create a python file in the current folder, which will print hello, "
        "execute it, and show the output.",
    )
    latency_s = time.monotonic() - t0

    # Detect newly created .py files.
    py_files_after = set(f for f in os.listdir(cwd) if f.endswith(".py"))
    new_py_files = py_files_after - py_files_before

    print(f"\n[E2E #3 create+run] latency={latency_s:.1f}s")
    print(f"[E2E #3 create+run] new .py files on disk: {new_py_files}")
    print(f"[E2E #3 create+run] response={response!r}")

    assert isinstance(response, str), "response must be a str"
    assert response.strip(), "response must not be empty / whitespace-only"
    assert not response.startswith("[Error:"), (
        f"Agent returned an error-path response: {response!r}"
    )

    # Primary assertion: response must contain 'hello' (the printed output).
    assert "hello" in response.lower(), (
        f"Response does not contain 'hello' — the Python file may not have been "
        f"executed or output not captured.\nResponse was: {response!r}"
    )

    # Secondary assertion: at least one new .py file should exist on disk.
    assert new_py_files, (
        f"No new .py files were created on disk in {cwd!r}.\n"
        f"Files before: {py_files_before}\n"
        f"Files after: {py_files_after}\n"
        f"Response was: {response!r}"
    )

    # Log the created file path for the report.
    for fname in new_py_files:
        fpath = os.path.join(cwd, fname)
        print(f"[E2E #3 create+run] file created: {fpath}")

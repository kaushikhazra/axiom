"""Context-window sizing: forced failures, not just handler inspection.

AC 5 (no max reported) and AC 3/4 (min of the two, shown) are already
demonstrated live - see cycle-2's log. These force the paths that
weren't: AC 6 (memory query fails), AC 9 (both fail together).

The backend is injected. psutil is still patched, because it is a real
dependency of context.py rather than part of the model seam.
"""

import psutil
import pytest

import axiom
from conftest import StubBackend, feed

QWEN_2_5_7B_INFO = {
    "qwen2.context_length": 32768,
    "qwen2.block_count": 28,
    "qwen2.attention.head_count": 28,
    "qwen2.attention.head_count_kv": 4,
    "qwen2.embedding_length": 3584,
}


def feed_and_exit(monkeypatch) -> None:
    feed(monkeypatch, ["hi", "/exit"])


def break_memory(monkeypatch) -> None:
    def broken_virtual_memory():
        raise OSError("cannot read /proc/meminfo")

    monkeypatch.setattr(psutil, "virtual_memory", broken_virtual_memory)


def test_memory_query_failure_falls_back_to_model_max(monkeypatch, capsys):
    """AC 6: psutil itself raising must not crash the program."""
    break_memory(monkeypatch)
    feed_and_exit(monkeypatch)

    axiom.main([], using=StubBackend(info=QWEN_2_5_7B_INFO))

    out = capsys.readouterr().out
    assert "context: 32768 tokens" in out, (
        "memory query failing should still let the model's own max context resolve"
    )


def test_both_queries_failing_falls_back_to_ollama_default(monkeypatch, capsys):
    """AC 9: model info AND memory both unavailable -> Ollama's own default, no crash.

    info=None is what a backend reports when the model cannot be asked - that
    the Ollama backend turns a ResponseError into exactly that is proved
    directly in test_backend.py.
    """
    backend = StubBackend(info=None)
    break_memory(monkeypatch)
    feed_and_exit(monkeypatch)

    axiom.main([], using=backend)

    out = capsys.readouterr().out
    assert "context: Ollama default" in out
    assert "None" not in out.split("\n")[0], (
        "must not print a fabricated context number"
    )
    assert backend.options == [None], (
        "nothing to size num_ctx from - must omit it entirely"
    )


def test_available_memory_returns_none_on_failure(monkeypatch):
    """Unit-level: the wrapper itself, not just the end-to-end behaviour above."""

    def broken_virtual_memory():
        raise OSError("boom")

    monkeypatch.setattr(psutil, "virtual_memory", broken_virtual_memory)
    assert axiom.context.available_memory() is None


@pytest.mark.parametrize(
    ("model_info", "expected_context"),
    [
        (QWEN_2_5_7B_INFO, 32768),
        ({**QWEN_2_5_7B_INFO, "qwen2.context_length": 262144}, 262144),
    ],
)
def test_context_length_is_requeried_per_run(
    monkeypatch, capsys, model_info, expected_context
):
    """AC 8: a fresh run with a different model reflects a different context.

    Each parametrize case is an independent process-equivalent run (a fresh
    axiom.main() call), which is what proves this is a per-run query and not
    a value cached across the module or process lifetime.
    """
    # Isolate the model side: give memory a budget larger than either case's
    # max context, so this machine's real available RAM can't cap the result
    # and hide whether the model query actually re-ran.
    monkeypatch.setattr(
        psutil, "virtual_memory", lambda: type("VM", (), {"available": 10**15})()
    )
    feed_and_exit(monkeypatch)

    axiom.main([], using=StubBackend(info=model_info))

    out = capsys.readouterr().out
    assert f"context: {expected_context} tokens" in out


def test_debug_max_context_env_var_overrides_the_computed_value(monkeypatch, capsys):
    """AXIOM_DEBUG_MAX_CONTEXT exists to make manual/local testing of the
    compaction ladder (#29) practical without needing a real conversation
    large enough to fill a real model's actual context.
    """
    monkeypatch.setenv("AXIOM_DEBUG_MAX_CONTEXT", "500")
    feed_and_exit(monkeypatch)

    axiom.main([], using=StubBackend(info=QWEN_2_5_7B_INFO))

    out = capsys.readouterr().out
    assert "context: 500 tokens, debug override" in out


def test_debug_max_context_env_var_unset_uses_the_normal_computation(
    monkeypatch, capsys
):
    monkeypatch.delenv("AXIOM_DEBUG_MAX_CONTEXT", raising=False)
    feed_and_exit(monkeypatch)

    axiom.main([], using=StubBackend(info=QWEN_2_5_7B_INFO))

    out = capsys.readouterr().out
    assert "debug override" not in out

"""Context-window sizing: forced failures, not just handler inspection.

AC 5 (no max reported) and AC 3/4 (min of the two, shown) are already
demonstrated live - see cycle-2's log. These force the paths that
weren't: AC 6 (memory query fails), AC 9 (both fail together).
"""

import builtins

import psutil
import pytest

import axiom


class ShowOnlyClient:
    """A client that only implements .show() - enough for these tests."""

    def __init__(self, model_info: dict) -> None:
        self._model_info = model_info

    def show(self, model):  # noqa: ANN001, ARG002
        return type("Info", (), {"modelinfo": self._model_info})()

    def chat(self, model, messages, stream, options=None):  # noqa: ANN001, ARG002
        assert (
            options is None
            or "num_ctx" not in options
            or options["num_ctx"] is not None
        )
        return iter(
            [type("Chunk", (), {"message": type("Msg", (), {"content": "ok"})()})()]
        )


QWEN_2_5_7B_INFO = {
    "qwen2.context_length": 32768,
    "qwen2.block_count": 28,
    "qwen2.attention.head_count": 28,
    "qwen2.attention.head_count_kv": 4,
    "qwen2.embedding_length": 3584,
}


def feed_and_exit(monkeypatch) -> None:
    supply = iter(["hi", "/exit"])

    def fake_input(prompt: str = "") -> str:
        print(prompt, end="")
        return next(supply)

    monkeypatch.setattr(builtins, "input", fake_input)


def test_memory_query_failure_falls_back_to_model_max(monkeypatch, capsys):
    """AC 6: psutil itself raising must not crash the program."""
    monkeypatch.setattr(
        axiom.ollama, "Client", lambda host: ShowOnlyClient(QWEN_2_5_7B_INFO)
    )

    def broken_virtual_memory():
        raise OSError("cannot read /proc/meminfo")

    monkeypatch.setattr(psutil, "virtual_memory", broken_virtual_memory)
    feed_and_exit(monkeypatch)

    axiom.main([])

    out = capsys.readouterr().out
    assert "context: 32768 tokens" in out, (
        "memory query failing should still let the model's own max context resolve"
    )


def test_both_queries_failing_falls_back_to_ollama_default(monkeypatch, capsys):
    """AC 9: model info AND memory both unavailable -> Ollama's own default, no crash."""

    class BrokenClient:
        def show(self, model):  # noqa: ANN001, ARG002
            raise axiom.ollama.ResponseError("model not found", 404)

        def chat(self, model, messages, stream, options=None):  # noqa: ANN001, ARG002
            assert options is None, (
                "nothing to size num_ctx from - must omit it entirely"
            )
            return iter(
                [type("Chunk", (), {"message": type("Msg", (), {"content": "ok"})()})()]
            )

    monkeypatch.setattr(axiom.ollama, "Client", lambda host: BrokenClient())

    def broken_virtual_memory():
        raise OSError("cannot read /proc/meminfo")

    monkeypatch.setattr(psutil, "virtual_memory", broken_virtual_memory)
    feed_and_exit(monkeypatch)

    axiom.main([])

    out = capsys.readouterr().out
    assert "context: Ollama default" in out
    assert "None" not in out.split("\n")[0], (
        "must not print a fabricated context number"
    )


def test_available_memory_returns_none_on_failure(monkeypatch):
    """Unit-level: the wrapper itself, not just the end-to-end behaviour above."""

    def broken_virtual_memory():
        raise OSError("boom")

    monkeypatch.setattr(psutil, "virtual_memory", broken_virtual_memory)
    assert axiom.available_memory() is None


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
    monkeypatch.setattr(axiom.ollama, "Client", lambda host: ShowOnlyClient(model_info))
    # Isolate the model side: give memory a budget larger than either case's
    # max context, so this machine's real available RAM can't cap the result
    # and hide whether the model query actually re-ran.
    monkeypatch.setattr(
        psutil,
        "virtual_memory",
        lambda: type("VM", (), {"available": 10**15})(),
    )
    feed_and_exit(monkeypatch)

    axiom.main([])

    out = capsys.readouterr().out
    assert f"context: {expected_context} tokens" in out

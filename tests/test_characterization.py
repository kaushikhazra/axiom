"""Golden-master transcript of everything a user can observe.

#33 AC 1 requires observable behaviour to be identical after the restructure.
That cannot be settled by reasoning about the code - the whole risk of a
refactor is that it looks right and behaves differently. So this module drives
main() down every observable path against stub clients, captures stdout,
stderr and how the run ended, and compares the whole transcript against
tests/baseline/transcript.txt.

The baseline is regenerated only on purpose:

    AXIOM_WRITE_BASELINE=1 uv run pytest -k characterization

Regenerating it to make a failure go away is the one thing that defeats the
point of having it.
"""

import contextlib
import io
import os
from pathlib import Path

import httpx
import ollama
import psutil
import pytest

import axiom
from conftest import chunk, feed

BASELINE = Path(__file__).parent / "baseline" / "transcript.txt"

# Fixed so the memory-derived context budget cannot vary with the machine.
FIXED_AVAILABLE_BYTES = 8 * 1024**3

# Full enough to exercise the KV-cache path; context_length still wins the min().
FULL_INFO = {
    "qwen2.context_length": 32768,
    "qwen2.block_count": 28,
    "qwen2.attention.head_count_kv": 4,
    "qwen2.attention.key_length": 128,
}


def _reply(text: str):
    return type("Reply", (), {"message": type("Msg", (), {"content": text})()})()


class StubClient:
    """Covers both call shapes: the streaming chat loop and the plain summary call.

    `turns` is one list of actions per streamed turn. A string is yielded as a
    chunk; an exception instance is raised at that point in the stream.
    """

    def __init__(
        self,
        info: dict | None = None,
        turns: list | None = None,
        summary: str = "a short summary",
        prompt_eval_count: int = 1,
        show_raises: BaseException | None = None,
    ) -> None:
        self.info = FULL_INFO if info is None else info
        self.turns = list(turns or [])
        self.summary = summary
        self.prompt_eval_count = prompt_eval_count
        self.show_raises = show_raises
        self.index = 0

    def show(self, model):  # noqa: ANN001, ARG002
        if self.show_raises is not None:
            raise self.show_raises
        return type(
            "Info",
            (),
            {"modelinfo": self.info, "capabilities": ["completion", "tools"]},
        )()

    def chat(self, model, messages, stream=False, options=None, tools=None):  # noqa: ANN001, ARG002
        if not stream:
            return _reply(self.summary)
        actions = (
            self.turns[self.index] if self.index < len(self.turns) else ["a reply"]
        )
        self.index += 1
        return self._stream(actions)

    def _stream(self, actions):
        for action in actions:
            if isinstance(action, BaseException):
                raise action
            yield chunk(action, self.prompt_eval_count, 0)


def _run(name: str, lines: list, client: StubClient, debug_context: str | None) -> str:
    out, err = io.StringIO(), io.StringIO()
    ending = "returned normally (exit status 0)"

    with pytest.MonkeyPatch.context() as mp:
        # Explicitly isolated: this variable leaks in from live compaction runs,
        # and six existing tests inherit whatever the ambient environment holds.
        mp.delenv("AXIOM_DEBUG_MAX_CONTEXT", raising=False)
        if debug_context is not None:
            mp.setenv("AXIOM_DEBUG_MAX_CONTEXT", debug_context)
        mp.setattr(axiom.backend.ollama, "Client", lambda host: client)  # noqa: ARG005
        mp.setattr(
            psutil,
            "virtual_memory",
            lambda: type("VM", (), {"available": FIXED_AVAILABLE_BYTES})(),
        )
        feed(mp, lines)
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            try:
                axiom.main([])
            except SystemExit as exit_called:
                ending = f"SystemExit({exit_called.code})"
            except BaseException as escaped:  # noqa: BLE001
                ending = f"escaped {type(escaped).__name__}: {escaped}"

    return (
        f"=== {name} ===\n"
        f"--- stdout ---\n{out.getvalue()}\n"
        f"--- stderr ---\n{err.getvalue()}\n"
        f"--- ending --- {ending}\n\n"
    )


def _scenarios() -> list[tuple[str, list, StubClient, str | None]]:
    """Built fresh on every call - a stub carries per-run state."""
    return [
        (
            "startup reports the model, host and context",
            ["/exit"],
            StubClient(),
            None,
        ),
        (
            "startup when the model cannot be reached",
            ["/exit"],
            StubClient(show_raises=ConnectionError("connection refused")),
            None,
        ),
        (
            "a normal exchange",
            ["hello", "/exit"],
            StubClient(turns=[["hi ", "there"]]),
            None,
        ),
        (
            "a blank line is ignored",
            ["", "   ", "/exit"],
            StubClient(),
            None,
        ),
        (
            "compaction fires and says so",
            ["first message", "second message", "/exit"],
            StubClient(prompt_eval_count=190),
            "200",
        ),
        (
            "a model error mid-turn",
            ["hello", "/exit"],
            StubClient(turns=[[ollama.ResponseError("model not found")]]),
            None,
        ),
        (
            "the connection drops before any reply arrives",
            ["hello", "/exit"],
            StubClient(turns=[[httpx.ConnectError("connection refused")]]),
            None,
        ),
        (
            "the connection drops mid-reply",
            ["hello", "/exit"],
            StubClient(turns=[["partial ", httpx.ReadError("connection reset")]]),
            None,
        ),
        (
            "Ctrl-C during generation cancels only that reply",
            ["hello", "again", "/exit"],
            StubClient(turns=[["partial ", KeyboardInterrupt()], ["second reply"]]),
            None,
        ),
        (
            "Ctrl-C at an idle prompt exits",
            [KeyboardInterrupt()],
            StubClient(),
            None,
        ),
        (
            "/exit leaves",
            ["/exit"],
            StubClient(),
            None,
        ),
        (
            "/quit leaves",
            ["/quit"],
            StubClient(),
            None,
        ),
        (
            "end of input leaves",
            [],
            StubClient(),
            None,
        ),
    ]


def test_observable_behaviour_matches_the_baseline():
    """AC 1: the restructure must not change anything the user can see."""
    transcript = "".join(_run(*scenario) for scenario in _scenarios())

    if os.environ.get("AXIOM_WRITE_BASELINE"):
        BASELINE.parent.mkdir(parents=True, exist_ok=True)
        BASELINE.write_text(transcript, encoding="utf-8")
        pytest.skip(f"baseline rewritten: {BASELINE}")

    assert BASELINE.exists(), (
        f"no baseline at {BASELINE} - regenerate with AXIOM_WRITE_BASELINE=1"
    )
    recorded = BASELINE.read_text(encoding="utf-8")
    assert transcript.splitlines() == recorded.splitlines(), (
        "observable behaviour changed against the recorded baseline"
    )

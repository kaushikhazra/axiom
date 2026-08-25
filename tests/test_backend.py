"""The seam itself: what OllamaBackend does with what the vendor client throws.

The session tests inject a stub backend and never see a vendor exception, so
the translation from ollama/httpx errors into this module's own family is
covered here, at the only boundary where those types still exist.
"""

import httpx
import ollama
import pytest

from axiom.backend import BackendError, ConnectionLost, OllamaBackend
from conftest import chunk


class Client:
    """Stands in for ollama.Client."""

    def __init__(
        self,
        info: dict | None = None,
        show_raises: BaseException | None = None,
        capabilities: tuple = ("completion", "tools"),
        chunks: tuple = (),
        stream_raises: BaseException | None = None,
        summary: str | None = "a summary",
    ) -> None:
        self.info = {} if info is None else info
        self.capabilities = list(capabilities)
        self.show_raises = show_raises
        self.chunks = list(chunks)
        self.stream_raises = stream_raises
        self.summary = summary

    def show(self, model):  # noqa: ANN001, ARG002
        if self.show_raises is not None:
            raise self.show_raises
        return type(
            "Info", (), {"modelinfo": self.info, "capabilities": self.capabilities}
        )()

    def chat(self, model, messages, stream=False, options=None, tools=None):  # noqa: ANN001, ARG002
        if not stream:
            return type(
                "Reply", (), {"message": type("Msg", (), {"content": self.summary})()}
            )()
        return self._stream()

    def _stream(self):
        for piece in self.chunks:
            yield piece
        if self.stream_raises is not None:
            raise self.stream_raises


@pytest.fixture
def backend_for(monkeypatch):
    def make(client: Client) -> OllamaBackend:
        monkeypatch.setattr(ollama, "Client", lambda host: client)  # noqa: ARG005
        return OllamaBackend("http://test")

    return make


@pytest.mark.parametrize(
    "failure",
    [
        ollama.ResponseError("model not found", 404),
        ConnectionError("connection refused"),
        httpx.ReadError("connection reset"),
    ],
)
def test_model_info_is_none_when_the_model_cannot_be_asked(backend_for, failure):
    """Every way asking can fail collapses to None - the caller sizes context
    from what it has, and there is nothing to size from."""
    assert backend_for(Client(show_raises=failure)).model_info("m") is None


def test_model_info_returns_a_dict_when_the_model_reports_nothing(backend_for):
    """An empty modelinfo is still an answer and must not read as a failure -
    None means "could not ask", and the two produce different startup lines."""
    assert backend_for(Client(info={})).model_info("m") == {}


def test_a_refused_request_becomes_a_backend_error(backend_for):
    backend = backend_for(Client(stream_raises=ollama.ResponseError("nope", 400)))
    with pytest.raises(BackendError) as raised:
        list(backend.stream("m", [], None))
    assert not isinstance(raised.value, ConnectionLost), (
        "a refusal is not a lost connection - they carry different advice"
    )
    assert "nope" in str(raised.value), "the vendor's own wording must survive"


@pytest.mark.parametrize(
    "failure",
    [
        ConnectionError("refused"),
        httpx.ConnectError("refused"),
        httpx.ReadError("reset"),
    ],
)
def test_transport_failures_become_connection_lost(backend_for, failure):
    backend = backend_for(Client(stream_raises=failure))
    with pytest.raises(ConnectionLost):
        list(backend.stream("m", [], None))


def test_pieces_carry_the_text_and_the_summed_usage(backend_for):
    backend = backend_for(Client(chunks=(chunk("hi ", 10, 1), chunk("there", 10, 4))))
    pieces = list(backend.stream("m", [], None))
    assert [p.text for p in pieces] == ["hi ", "there"]
    assert [p.usage for p in pieces] == [11, 14], (
        "usage is prompt_eval_count + eval_count, and the last piece is what counts"
    )


def test_a_partial_stream_yields_before_it_raises(backend_for):
    """What arrived before the drop must reach the caller - the session prints
    it, and reports how much of it there was."""
    backend = backend_for(
        Client(chunks=(chunk("partial "),), stream_raises=httpx.ReadError("reset"))
    )
    seen = []
    with pytest.raises(ConnectionLost):
        for piece in backend.stream("m", [], None):
            seen.append(piece.text)
    assert seen == ["partial "]


def test_complete_returns_the_reply_text(backend_for):
    assert backend_for(Client(summary="summarized")).complete("m", []) == "summarized"


def test_complete_turns_a_blank_reply_into_an_empty_string(backend_for):
    assert backend_for(Client(summary=None)).complete("m", []) == ""

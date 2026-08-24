"""A terminal chat with a local Ollama model."""

from . import backend, compaction, config, context, terminal
from .backend import ModelBackend

EXIT_COMMANDS = {"/exit", "/quit"}


def main(argv: list[str] | None = None, using: ModelBackend | None = None) -> None:
    settings = config.resolve(argv)
    model_backend = using or backend.OllamaBackend(settings.host)

    effective_context = context.effective_context(
        model_backend.model_info(settings.model)
    )
    if settings.debug_max_context is not None:
        effective_context = settings.debug_max_context

    chat_options = (
        {"num_ctx": effective_context} if effective_context is not None else None
    )
    terminal.announce(
        settings.model,
        settings.host,
        effective_context,
        overridden=settings.debug_max_context is not None,
    )

    messages: list[dict[str, str]] = []
    running_usage: int | None = None  # real prompt_eval_count + eval_count, last turn

    while True:
        line = terminal.read_line()
        if line is None or line in EXIT_COMMANDS:
            return
        if not line:
            continue

        messages, kept_pairs = compaction.maybe_compact(
            model_backend, settings.model, messages, running_usage, effective_context
        )
        if kept_pairs is not None:
            terminal.note_compaction(kept_pairs)

        messages.append({"role": "user", "content": line})
        reply = ""
        last_usage = None
        try:
            for piece in model_backend.stream(settings.model, messages, chat_options):
                reply += piece.text
                terminal.show_piece(piece.text)
                last_usage = piece.usage
        except (KeyboardInterrupt, backend.BackendError) as failure:
            # The half-finished answer does not become history.
            messages.pop()
            terminal.report_failure(failure, reply, settings.host)
            continue

        terminal.end_reply()
        messages.append({"role": "assistant", "content": reply})
        if last_usage is not None:
            running_usage = last_usage

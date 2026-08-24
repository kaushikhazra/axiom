"""A terminal chat with a local Ollama model."""

import sys

from . import backend, compaction, config, context

EXIT_COMMANDS = {"/exit", "/quit"}


def report_failure(failure: BaseException, reply: str, host: str) -> None:
    """The one place a failed turn is reported.

    Three ways a turn can fail - cancelled, refused, connection lost - and one
    handler, because by the time a failure arrives here it is either an
    interrupt or a single error family. The leading blank line separates the
    message from a partial reply already on screen; a cancellation always gets
    one, because the user pressed the key mid-line.
    """
    if isinstance(failure, KeyboardInterrupt):
        message = f"cancelled after {len(reply)} characters"
    elif isinstance(failure, backend.ConnectionLost) and reply:
        # Part of a reply is already on screen. Say so, or the user reads a
        # fragment as though it were the whole answer.
        message = (
            f"error: reply cut off after {len(reply)} characters "
            f"- lost connection to {host} ({failure})"
        )
    elif isinstance(failure, backend.ConnectionLost):
        message = f"error: cannot reach Ollama at {host} ({failure})"
    else:
        message = f"error: {failure}"

    if reply or isinstance(failure, KeyboardInterrupt):
        print(file=sys.stderr)
    print(message, file=sys.stderr)


def main(argv: list[str] | None = None) -> None:
    settings = config.resolve(argv)
    model_backend = backend.OllamaBackend(settings.host)

    effective_context = context.effective_context(
        model_backend.model_info(settings.model)
    )

    context_note_suffix = ""
    if settings.debug_max_context is not None:
        effective_context = settings.debug_max_context
        context_note_suffix = ", debug override"

    chat_options = (
        {"num_ctx": effective_context} if effective_context is not None else None
    )
    context_note = (
        f"{effective_context} tokens{context_note_suffix}"
        if effective_context is not None
        else "Ollama default"
    )
    print(f"axiom: {settings.model} at {settings.host} (context: {context_note})")

    messages: list[dict[str, str]] = []
    running_usage: int | None = None  # real prompt_eval_count + eval_count, last turn

    while True:
        try:
            line = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            # Ctrl-C at an idle prompt means leave, same as Ctrl-D.
            print()
            return

        if not line:
            continue
        if line in EXIT_COMMANDS:
            return

        messages, kept_pairs = compaction.maybe_compact(
            model_backend, settings.model, messages, running_usage, effective_context
        )
        if kept_pairs is not None:
            level = (
                "everything" if kept_pairs == 0 else f"keeping the last {kept_pairs}"
            )
            print(f"axiom: compacting older history ({level})")

        messages.append({"role": "user", "content": line})
        reply = ""
        last_usage = None
        try:
            for piece in model_backend.stream(settings.model, messages, chat_options):
                reply += piece.text
                print(piece.text, end="", flush=True)
                last_usage = piece.usage
        except (KeyboardInterrupt, backend.BackendError) as failure:
            # The half-finished answer does not become history.
            messages.pop()
            report_failure(failure, reply, settings.host)
            continue

        print()
        messages.append({"role": "assistant", "content": reply})
        if last_usage is not None:
            running_usage = last_usage

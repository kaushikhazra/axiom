"""A terminal chat with a local Ollama model."""

from . import backend, compaction, config, context, terminal, tools
from .backend import Call, ModelBackend

EXIT_COMMANDS = {"/exit", "/quit"}

# A turn may go model -> tool -> model more than once, but not forever: a model
# that keeps calling tools without answering would otherwise never hand back.
MAX_TOOL_ROUNDS = 5


def main(argv: list[str] | None = None, using: ModelBackend | None = None) -> None:
    settings = config.resolve(argv)
    model_backend = using or backend.OllamaBackend(settings.host)

    # Asked once, before anything is sent: a model with no tool support is told
    # nothing about tools rather than being sent some and refusing.
    declarations = (
        tools.declarations() if model_backend.supports_tools(settings.model) else None
    )

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

        before = len(messages)
        messages.append({"role": "user", "content": line})
        reply = ""
        last_usage = None
        try:
            for _round in range(MAX_TOOL_ROUNDS):
                reply, calls = "", []
                for event in model_backend.stream(
                    settings.model, messages, chat_options, declarations
                ):
                    if isinstance(event, Call):
                        calls.append(event)
                        continue
                    reply += event.text
                    terminal.show_piece(event.text)
                    last_usage = event.usage
                if not calls:
                    break

                # The model asked for work before answering. Its own turn goes
                # back into history first, or it cannot match the results to
                # what it asked for.
                if reply:
                    terminal.end_reply()
                messages.append(
                    {
                        "role": "assistant",
                        "content": reply,
                        "tool_calls": [call.as_message_part() for call in calls],
                    }
                )
                for call in calls:
                    terminal.note_tool(call.name, call.arguments)
                    result = tools.run(call.name, call.arguments)
                    terminal.show_tool_result(result)
                    messages.append(
                        {"role": "tool", "content": result, "tool_name": call.name}
                    )
        except (KeyboardInterrupt, backend.BackendError) as failure:
            # Nothing from a failed turn becomes history - including any tool
            # results already gathered during it.
            del messages[before:]
            terminal.report_failure(failure, reply, settings.host)
            continue

        terminal.end_reply()
        messages.append({"role": "assistant", "content": reply})
        if last_usage is not None:
            running_usage = last_usage

"""A terminal chat with a local Ollama model."""

from . import backend, compaction, config, context, terminal, tools
from .backend import Call, ModelBackend

EXIT_COMMANDS = {"/exit", "/quit"}

# A turn may go model -> tool -> model more than once, but not forever: a model
# that keeps calling tools without answering would otherwise never hand back.
#
# Eight rather than five on evidence: qwen2.5-coder was observed re-issuing an
# identical call four times before answering a single-step question. It is not
# deterministic - the same question answered in one round on a rerun - but a
# genuine multi-step request plus that behaviour would have hit a bound of five
# and returned an empty answer. The bound is here to stop a runaway, not to
# ration work a model legitimately needs.
MAX_TOOL_ROUNDS = 8


def _could_still_be_a_call(reply: str) -> bool:
    """Whether a part-finished reply might yet turn out to be a call in text.

    A call announced as text is JSON, so it opens with a brace. Once the reply
    opens with anything else it is an answer, and holding it back would be
    withholding the thing the user asked for.
    """
    leading = reply.lstrip()
    return leading == "" or leading.startswith("{")


def main(argv: list[str] | None = None, using: ModelBackend | None = None) -> None:
    settings = config.resolve(argv)
    model_backend = using or backend.OllamaBackend(settings.host)

    # Asked once, before anything is sent: a model with no tool support is told
    # nothing about tools rather than being sent some and refusing. `available`
    # is None for "cannot", 0 for "switched off", a count otherwise - three
    # states the startup line reports differently.
    capable = model_backend.supports_tools(settings.model)
    declarations = tools.declarations() if capable and settings.tools_enabled else None
    if declarations is not None and not settings.web_enabled:
        declarations = [
            tool
            for tool in declarations
            if tool["function"]["name"] not in tools.WEB_TOOLS
        ]
    available = len(declarations) if declarations else (0 if capable else None)
    limits = tools.Limits(
        working_directory=settings.working_directory,
        command_timeout=settings.command_timeout,
        search_results=settings.search_results,
        fetch_timeout=settings.fetch_timeout,
        page_characters=settings.page_characters,
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
        tools=available,
        web=settings.web_enabled,
    )

    messages: list[dict[str, str]] = []
    running_usage: int | None = None  # real prompt_eval_count + eval_count, last turn

    while True:
        line = terminal.read_line()
        if line is None or line in EXIT_COMMANDS:
            return
        if not line:
            continue

        messages, kept_pairs, _shrunk = compaction.maybe_compact(
            model_backend, settings.model, messages, running_usage, effective_context
        )
        if kept_pairs is not None:
            terminal.note_compaction(kept_pairs)

        before = len(messages)
        messages.append({"role": "user", "content": line})
        reply = ""
        last_usage = None
        last_prompt_usage = None
        # Per turn, never cumulative: last question's sources are not this
        # answer's. `read` is pages actually retrieved; `seen` is addresses a
        # search returned. Only the first are sources.
        read: list[str] = []
        seen: list[str] = []

        # Checked after compaction has had its chance: if it still will not
        # fit, sending it means Ollama cuts it silently and the model answers
        # from a fragment.
        over = compaction.too_large(messages, effective_context)
        if over is not None:
            terminal.report_too_large(over)
            del messages[before:]
            continue
        sent_estimate = compaction.estimated_tokens(messages)
        try:
            for _round in range(MAX_TOOL_ROUNDS):
                reply, calls, shown = "", [], 0
                # Some models announce a call as bare JSON in the reply, token
                # by token, so no single piece is recognisable. Hold the reply
                # back only while it could still turn out to be one - and let
                # it through the moment it cannot, or streaming would be lost
                # for every model that behaves.
                withholding = declarations is not None
                for event in model_backend.stream(
                    settings.model, messages, chat_options, declarations
                ):
                    if isinstance(event, Call):
                        calls.append(event)
                        continue
                    reply += event.text
                    last_usage = event.usage
                    last_prompt_usage = event.prompt_usage
                    if withholding and not _could_still_be_a_call(reply):
                        withholding = False
                    if not withholding:
                        terminal.show_piece(reply[shown:])
                        shown = len(reply)

                if withholding:
                    announced = backend.call_from_text(reply, set(tools.REGISTRY))
                    if announced is not None:
                        calls.append(announced)
                        reply = ""  # the text was the call, not an answer
                    else:
                        terminal.show_piece(reply[shown:])

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
                    result = tools.run(call.name, call.arguments, limits)
                    if call.name == "fetch_page" and not result.startswith("error:"):
                        read.append(str(call.arguments.get("url")))
                    elif call.name == "search_web":
                        seen.extend(tools.addresses_in(result))
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
        if compaction.looks_truncated(sent_estimate, last_prompt_usage):
            terminal.report_truncated(sent_estimate, last_prompt_usage)
        terminal.show_sources(read, seen)
        messages.append({"role": "assistant", "content": reply})
        if last_usage is not None:
            running_usage = last_usage

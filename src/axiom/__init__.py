"""A terminal chat with a local Ollama model."""

import json
import sys

from . import backend, compaction, config, context, models, servers, terminal, tools
from .backend import Call, ModelBackend

EXIT_COMMANDS = {"/exit", "/quit"}

# What a run exits with when it could not start at all. Distinct from 0, which
# every ordinary way out uses - /exit, end of input, Ctrl-C - because a script
# that pipes into axiom needs to tell "it ran and finished" from "it never got
# a model." Nothing in axiom exited non-zero before this.
CANNOT_START = 2

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
    attached = servers.Servers(
        settings.mcp_servers,
        start_timeout=settings.mcp_start_timeout,
        call_timeout=settings.mcp_call_timeout,
    )
    try:
        _chat(settings, attached, using)
    finally:
        # Every route out goes through here - /exit, end of input, Ctrl-C, a
        # session that cannot continue, or an exception on the way. A server
        # that outlived axiom would be work happening that nobody is waiting
        # for and nobody can see.
        attached.stop()


def _settle_model(
    model_backend: ModelBackend, settings: config.Settings, interactive: bool
) -> str | None:
    """Which model this run uses. None means the user left before choosing.

    Everything here happens before a server is started or a tool is declared
    (AC 1). Two conditions end the run outright - a host that cannot be reached
    and a host with nothing on it - because neither has a model to offer and
    carrying on would mean inventing one, which is the whole defect this
    replaces.
    """
    try:
        available = model_backend.installed()
    except backend.BackendError as unreachable:
        terminal.report_no_host(settings.host, unreachable)
        sys.exit(CANNOT_START)
    if not available:
        terminal.report_no_models(settings.host)
        sys.exit(CANNOT_START)

    if models.unreadable():
        terminal.note_choice_unreadable(str(models.DEFAULT_CHOICE_FILE))

    decision = models.choose(settings.model, available, settings.host, interactive)
    if decision.missing:
        terminal.note_model_missing(decision.missing, settings.host)
    if decision.forgotten:
        terminal.note_choice_forgotten(decision.forgotten, settings.host)
    if decision.model is not None:
        terminal.note_settled(decision.model, decision.reason)
        return decision.model

    # Only a pick made here is remembered (AC 14). Everything above this line
    # settled without the user choosing anything - a flag, the single-model
    # case, the non-terminal fallback - and none of them writes.
    terminal.show_models(decision.installed, settings.host, decision.default)
    while True:
        answer = terminal.ask_model()
        if answer is None:
            return None
        chosen = models.picked(answer, decision.installed, decision.default)
        if chosen is not None:
            _remember(chosen, settings.host)
            return chosen
        terminal.refuse_model(answer, len(decision.installed))


def _remember(chosen: str, host: str) -> None:
    """Save the pick, and say so only when there is something worth saying."""
    fresh = not models.DEFAULT_CHOICE_FILE.parent.exists()
    problem = models.write_choice(chosen, host)
    terminal.note_choice_saved(
        problem, str(models.DEFAULT_CHOICE_FILE.parent) if fresh and not problem else ""
    )


def _chat(
    settings: config.Settings,
    attached: "servers.Servers",
    using: ModelBackend | None,
) -> None:
    model_backend = using or backend.OllamaBackend(settings.host)
    interactive = sys.stdin.isatty()
    model = _settle_model(model_backend, settings, interactive)
    if model is None:
        # Left at the list. Nothing has started yet, so there is nothing to
        # unwind and nothing went wrong - status 0, like any other way out.
        return

    # Asked once, before anything is sent: a model with no tool support is told
    # nothing about tools rather than being sent some and refusing. `available`
    # is None for "cannot", 0 for "switched off", a count otherwise - three
    # states the startup line reports differently.
    capable = model_backend.supports_tools(model)
    declarations = tools.declarations() if capable and settings.tools_enabled else None
    if declarations is not None and not settings.web_enabled:
        declarations = [
            tool
            for tool in declarations
            if tool["function"]["name"] not in tools.WEB_TOOLS
        ]
    # Connected before the startup line is printed, so that line can report
    # what actually connected rather than what was asked for.
    if declarations is not None:
        # Said before the wait, not after: starting a server can take seconds,
        # and a silent pause before the first prompt reads as a hang.
        terminal.note_starting(len(settings.mcp_servers))
        attached.start()
        declarations = [*declarations, *attached.declarations]

    available = len(declarations) if declarations else (0 if capable else None)
    callable_names = {
        declaration["function"]["name"] for declaration in declarations or []
    }
    limits = tools.Limits(
        working_directory=settings.working_directory,
        command_timeout=settings.command_timeout,
        search_results=settings.search_results,
        fetch_timeout=settings.fetch_timeout,
        page_characters=settings.page_characters,
    )

    effective_context = context.effective_context(model_backend.model_info(model))
    if settings.debug_max_context is not None:
        effective_context = settings.debug_max_context

    chat_options = (
        {"num_ctx": effective_context} if effective_context is not None else None
    )
    terminal.announce(
        model,
        settings.host,
        effective_context,
        overridden=settings.debug_max_context is not None,
        tools=available,
        web=settings.web_enabled,
    )
    terminal.note_servers(
        attached.connected,
        [*settings.mcp_problems, *attached.failures],
        bounds=(settings.mcp_start_timeout, settings.mcp_call_timeout),
        cost=compaction.estimated_tokens(
            [
                {"role": "system", "content": json.dumps(declaration)}
                for declaration in declarations or []
            ]
        ),
        window=effective_context,
    )

    # Held here rather than in `messages`, deliberately. `compaction` treats a
    # leading system message as a carried-forward summary: a prompt at index 0
    # is absorbed into it, which suppresses the "Summary of earlier
    # conversation:" header, and its survival then depends on #32 happening to
    # forget the middle of the string rather than the front. Kept outside, none
    # of that is true and the model has its limits on every turn rather than
    # until the first compaction.
    instructions = {"role": "system", "content": tools.system_prompt(limits)}

    def to_send(history: list[dict[str, str]]) -> list[dict[str, str]]:
        """What actually goes to the model - and what the size checks must weigh."""
        return [instructions, *history]

    messages: list[dict[str, str]] = []
    running_usage: int | None = None  # real prompt_eval_count + eval_count, last turn

    while True:
        line = terminal.read_line()
        if line is None or line in EXIT_COMMANDS:
            return
        if not line:
            continue

        messages, kept_pairs, forgotten = compaction.maybe_compact(
            model_backend, model, messages, running_usage, effective_context
        )
        if kept_pairs is not None:
            terminal.note_compaction(kept_pairs)
        if forgotten:
            terminal.note_facts_forgotten(forgotten)

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
        # Weighed with the instructions included: they ride in every request,
        # so a check that only counts `messages` under-counts the real payload
        # by exactly the prompt, every turn.
        over = compaction.too_large(to_send(messages), effective_context)
        if over is not None and effective_context is not None:
            cause = compaction.what_will_not_fit(
                line, effective_context, len(instructions["content"])
            )
            # Checked before compacting, not after: when the fixed part alone
            # exceeds the context, no amount of compaction changes anything and
            # summarizing anyway costs a model call per doomed message.
            #
            # And said once, then out. AC 6 asks that the user be told plainly
            # "rather than discovering it by retrying" - repeating the same
            # unhelpable line at every prompt is that discovery, not an
            # alternative to it. Ending here is also what makes AC 4 true:
            # there is no state where every message is refused, because there
            # are no more messages.
            if cause == compaction.CANNOT_CONTINUE:
                terminal.report_too_large(over, cause)
                return

        if over is not None:
            # Refusing here without trying throws away a compaction that
            # usually rescues the turn. Measured: 1939 tokens down to 226
            # against a 2000 context, unattempted because the *previous*
            # turn's reported usage sat 50 tokens under the trigger. Driven by
            # the measurement rather than by usage, so it runs whatever the
            # last turn reported - including on a first turn, where usage is
            # None and compaction has never run at all.
            # The line the user just typed is held out of it. `maybe_compact`
            # runs *before* this line is appended, which is what keeps it to
            # history; `compact_to_fit` runs after, so without this the new
            # message is itself a compaction candidate. At kept_pairs=0 it was
            # replaced by a summary of itself and the model was sent a prompt
            # and "the user asked a long question" - answering a question it
            # had never seen, with nothing said about it. Worse than the
            # refusal it replaced.
            #
            # Passed as overhead instead: compact the history until the
            # history, the prompt and this message fit together.
            pending = messages.pop()
            messages, squeezed, let_go = compaction.compact_to_fit(
                model_backend,
                model,
                messages,
                effective_context,
                len(instructions["content"]) + len(pending["content"]),
            )
            messages.append(pending)
            # Reported through the same two lines a usage-triggered compaction
            # uses. A second path that forgot silently would undo #32.
            if squeezed is not None:
                terminal.note_compaction(squeezed)
            if let_go:
                terminal.note_facts_forgotten(let_go)
            # `before` indexed into the history as it was; compaction replaced
            # it with a shorter list. The user's line is still last, and that
            # is the only thing a refusal rolls back - whatever compaction
            # achieved is kept, or the next turn meets the same wall.
            before = len(messages) - 1
            over = compaction.too_large(to_send(messages), effective_context)

        if over is not None:
            terminal.report_too_large(
                over,
                compaction.what_will_not_fit(
                    line, effective_context, len(instructions["content"])
                ),
            )
            del messages[before:]
            continue
        sent_estimate = compaction.estimated_tokens(to_send(messages))
        # #41 AC 9, scoped to this turn and rebuilt with it. Keyed on the exact
        # command, holding the exact failures it gave: a command that fails
        # *differently* the second time is a new situation, and a different
        # command failing the same way is one too. Both halves are the
        # criterion.
        failures: dict[str, list[str]] = {}
        out_of_rounds = False
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
                    model, to_send(messages), chat_options, declarations
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
                    # Server tools are recognised here too, or a model that
                    # announces its calls as text could reach the built-ins
                    # and nothing else.
                    announced = backend.call_from_text(reply, callable_names)
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
                    arguments = (
                        call.arguments if isinstance(call.arguments, dict) else {}
                    )
                    terminal.note_tool(
                        call.name, call.arguments, tools.outside(arguments, limits)
                    )
                    command = arguments.get("command")
                    already = failures.get(command, [])
                    if len(already) >= 2 and already[-1] == already[-2]:
                        result = (
                            "error: this command has already failed twice in this "
                            "turn with the same result - not running it a third "
                            "time. Try something different or say what is wrong."
                        )
                    elif attached.owns(call.name):
                        # A server's tool is called and shown exactly like a
                        # built-in. The prefix routes it; nothing else in the
                        # loop knows the difference.
                        result = attached.run(call.name, arguments)
                    else:
                        result = tools.run(call.name, call.arguments, limits)
                        kind = tools.failure_kind(result)
                        if command is not None and kind:
                            failures.setdefault(command, []).append(kind)
                    if call.name == "fetch_page" and tools.was_read(result):
                        read.append(str(call.arguments.get("url")))
                    elif call.name == "search_web":
                        seen.extend(tools.addresses_in(result))
                    terminal.show_tool_result(result)
                    messages.append(
                        {"role": "tool", "content": result, "tool_name": call.name}
                    )
            else:
                # Ran every round and was still calling tools. Without this the
                # user gets whatever `reply` holds, which is nothing.
                out_of_rounds = True
        except (KeyboardInterrupt, backend.BackendError) as failure:
            # Nothing from a failed turn becomes history - including any tool
            # results already gathered during it.
            del messages[before:]
            terminal.report_failure(failure, reply, settings.host)
            continue

        terminal.end_reply()
        if out_of_rounds:
            terminal.note_round_limit(MAX_TOOL_ROUNDS)
        if compaction.looks_truncated(sent_estimate, last_prompt_usage):
            terminal.report_truncated(sent_estimate, last_prompt_usage)
        terminal.show_sources(read, seen)
        messages.append({"role": "assistant", "content": reply})
        if last_usage is not None:
            running_usage = last_usage

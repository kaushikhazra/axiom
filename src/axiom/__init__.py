"""A terminal chat with a local Ollama model."""

import json
import sys
from dataclasses import dataclass

from . import (
    backend,
    compaction,
    config,
    context,
    models,
    schedule,
    servers,
    terminal,
    tools,
)
from .backend import Call, ModelBackend

EXIT_COMMANDS = {"/exit", "/quit"}

# The third command, and the first that is not an exit. Matched as a whole
# word: a message that merely contains it is a message (#49 AC 9).
MODEL_COMMAND = "/model"

# Returned by a switch when the user ended the session at the list, as opposed
# to cancelling it. A sentinel rather than a second return value, because the
# ordinary answers are already "a new Running" and "nothing changed", and
# threading a flag through both would make the common case carry the rare one.
_LEAVING = object()

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

# How often an idle session looks at the clock, in seconds. Only ever reached
# when something is actually scheduled - a session with an empty schedule takes
# the blocking read it has always taken, and never wakes up at all.
#
# A quarter second because the finest schedule anyone can ask for is one a
# minute (#74 AC 29), so this is two hundred times finer than it needs to be and
# still costs nothing measurable. It bounds how late a job can be, not how often
# anything is computed.
SCHEDULE_TICK = 0.25


def _next_line(jobs: "schedule.Schedule | None") -> tuple[str | None, bool]:
    """What to act on next: what the user typed, or a job whose time has come.

    Returns the line, and whether it came from a schedule rather than a person.

    **With nothing scheduled this is the blocking read it has always been** - no
    thread, no timeout, no waking up. A session that never schedules anything
    cannot tell any of this exists, which is the same promise `read_line` makes.

    With something scheduled, the prompt is drawn here and the read is timed, so
    a job can fire while the user sits doing nothing. That is #74 AC 9, and it is
    the only reason any of this is here.

    AC 10 and AC 11 are structural rather than defended: this is called at the
    top of the loop and nowhere else, so a job cannot begin mid-turn, and one job
    is returned per pass, so two due at once run one after the other in the order
    `due()` gives them.
    """
    if jobs is None or not len(jobs):
        return terminal.read_line(), False
    terminal.show_prompt()
    while True:
        got = terminal.read_line(timeout=SCHEDULE_TICK)
        if got is not terminal.WAITING:
            return got, False  # a line, or None for leaving
        due = jobs.due()
        if not due:
            continue
        job = due[0]
        jobs.mark_run(job.id)
        # The prompt was drawn above and is about to be drawn over. Taking it
        # back first is what stops the turn reading as `> axiom: scheduled - ...`
        terminal.take_back_prompt()
        return job.prompt, True


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
    terminal.use_rendering(settings.render_enabled)
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

    # Passed as a callable, not a set: establishing tool support costs one
    # request per model, and `choose` only asks on the paths where the order
    # decides something the user did not (#52 AC 10).
    asked: dict[str, set[str]] = {}

    def capable() -> set[str]:
        asked["models"] = model_backend.tool_capable(list(available))
        return asked["models"]

    decision = models.choose(
        settings.model, available, settings.host, interactive, capable=capable
    )
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
    terminal.show_models(
        decision.installed, settings.host, decision.default, capable=asked.get("models")
    )
    while True:
        try:
            answer = terminal.ask_model()
        except (EOFError, KeyboardInterrupt):
            # Both mean leave. Nothing has started, so there is no session to
            # return to and no difference between the two worth drawing.
            return None
        chosen = models.picked(answer, decision.installed, decision.default)
        if chosen is not None:
            _remember(chosen, settings.host)
            return chosen
        terminal.refuse_model(answer, len(decision.installed))


@dataclass(frozen=True)
class Running:
    """Everything about a conversation that belongs to the model, not the session.

    These six move together and always for the same reason: the model changed.
    Held as one object rather than six locals so a switch is a single
    assignment - updating five of six is the failure mode that separate
    rebindings invite, and it would be silent.

    Everything *not* here is deliberately not here. The history, the tool
    limits, the working directory and the attached servers survive a switch
    untouched, and keeping them out of this object is what makes that
    structural rather than remembered (#49 AC 13, AC 14).
    """

    model: str
    capable: bool
    declarations: list[dict] | None
    callable_names: set[str]
    context: int | None
    options: dict | None

    @property
    def offered(self) -> int | None:
        """What the startup line reports: a count, 0 for off, None for cannot."""
        return (
            len(self.declarations)
            if self.declarations
            else (0 if self.capable else None)
        )


def _prepare(
    model_backend: ModelBackend,
    settings: config.Settings,
    attached: "servers.Servers",
    model: str,
) -> Running:
    """What this model can do, and how much room it has.

    Used at startup and again on every switch, so the two cannot drift. Tool
    support is asked once per model rather than discovered as a 400 at
    generation time - which would spend a request to find out, and would tell
    the user after they had already asked for something.

    Servers are started here on first need rather than at launch. A session
    that begins on a model with no tool support has none running, and switching
    to a capable model has to be able to bring them up - AC 16 promises the new
    model's tools, and a server that was never started is not one that is being
    restarted (AC 14).
    """
    capable = model_backend.supports_tools(model)
    declarations = tools.declarations() if capable and settings.tools_enabled else None
    if declarations is not None and not settings.web_enabled:
        declarations = [
            tool
            for tool in declarations
            if tool["function"]["name"] not in tools.WEB_TOOLS
        ]
    if declarations is not None:
        # Said before the wait, not after: starting a server can take seconds,
        # and a silent pause reads as a hang. Only when something will actually
        # be started - `start()` is a no-op once they are already up.
        if not attached.started:
            terminal.note_starting(len(settings.mcp_servers))
        attached.start()
        declarations = [*declarations, *attached.declarations]

    window = context.effective_context(model_backend.model_info(model))
    if settings.debug_max_context is not None:
        window = settings.debug_max_context

    return Running(
        model=model,
        capable=capable,
        declarations=declarations,
        callable_names={
            declaration["function"]["name"] for declaration in declarations or []
        },
        context=window,
        options={"num_ctx": window} if window is not None else None,
    )


def _switch_model(
    model_backend: ModelBackend,
    settings: config.Settings,
    attached: "servers.Servers",
    run: Running,
    named: str,
) -> "Running | object | None":
    """A model change asked for mid-conversation.

    Returns the new `Running`, `None` when nothing changed, or `_LEAVING` when
    the user ended the session at the list.

    Deliberately not `_settle_model`, which shares the pieces but not the
    policy. Four of its behaviours are wrong once a conversation exists: it
    exits the process when the host cannot be reached, where this carries on
    with the model already in use (AC 30); it treats Ctrl-C as leaving, where
    this cancels (AC 26); it marks the remembered model, where this marks the
    current one (AC 3); and it can settle without asking at all.

    What it does share is the list itself - `models.sorted_models` and
    `terminal.show_models` - which is the whole of AC 2. A second sorting
    implementation is how two lists drift apart.
    """
    try:
        listed = model_backend.installed()
        # Ordered the same way the startup list is (#49 AC 2), which now means
        # paying for tool support here too. Worth it: the switch list is shown
        # precisely so the user can pick, and a model that cannot call tools
        # sitting at the top is the thing #52 exists to stop.
        can_use_tools = model_backend.tool_capable(listed)
        available = models.sorted_models(listed, can_use_tools)
    except backend.BackendError as unreachable:
        # Not fatal here, unlike at startup. There is a working session with a
        # working model; failing to list the alternatives is a reason to stay
        # where we are, not to end it (AC 30, AC 32).
        terminal.report_switch_failed(settings.host, unreachable, run.model)
        return None

    if named:
        # Exact match, tag included. Ollama reads a bare `qwen2.5` as
        # `qwen2.5:latest` and would land on a model the user did not name -
        # the failure both stories exist to prevent. A near miss is reported
        # and falls through to the list (AC 7, AC 8).
        if named in available:
            return _switched_to(model_backend, settings, attached, run, named)
        terminal.note_model_missing(named, settings.host)

    # Shown even when there is nothing to choose (AC 27) and even when the
    # current model is not in it (AC 31) - the list is how the user sees where
    # they are, and withholding it to save a line leaves them guessing.
    terminal.show_models(
        available, settings.host, run.model, current=True, capable=can_use_tools
    )
    if run.model not in available:
        # AC 31. It cannot appear in the list - the list holds what the host
        # reports and nothing else - so the fact that it is still the model in
        # use has to be said outright, or nothing on screen is marked and the
        # user cannot tell what they are on.
        terminal.note_current_missing(run.model, settings.host)
    if len(available) == 1 and run.model in available:
        terminal.note_only_model(available[0])
        return None

    while True:
        try:
            answer = terminal.ask_model("enter to keep the current one")
        except KeyboardInterrupt:
            # "Never mind" - the session continues on the model it had. Unlike
            # at startup, there is something to return to (AC 26).
            terminal.note_unchanged(run.model)
            return None
        except EOFError:
            # Input has genuinely ended. There is nothing further to read, so
            # the session ends the same way end of input at the prompt does,
            # with status 0 (AC 33).
            return _LEAVING
        if not answer.strip():
            # Enter keeps the current model rather than re-choosing it. At
            # startup enter accepts a default; here there is nothing to accept,
            # and a switch nobody asked for is worse than a wasted keystroke.
            terminal.note_unchanged(run.model)
            return None
        # A number or an installed name. AC 25 refuses only what is *neither*,
        # so a user who already knows the name they want does not have to find
        # its number - and the name they would type at `/model <name>` is the
        # same one that works here.
        chosen = models.picked(answer, available, None) or (
            answer.strip() if answer.strip() in available else None
        )
        if chosen is not None:
            return _switched_to(model_backend, settings, attached, run, chosen)
        terminal.refuse_model(answer, len(available), names=True)


def _switched_to(
    model_backend: ModelBackend,
    settings: config.Settings,
    attached: "servers.Servers",
    run: Running,
    chosen: str,
) -> "Running | None":
    """Take the switch, remember it, and say what changed.

    Choosing the model already in use is accepted and changes nothing - it is
    not an error, and rebuilding `Running` would restart nothing but would
    still reset the usage count for no reason (AC 28).
    """
    if chosen == run.model:
        terminal.note_unchanged(chosen)
        return None
    _remember(chosen, settings.host)
    fresh = _prepare(model_backend, settings, attached, chosen)
    terminal.note_switched(
        fresh.model,
        fresh.context,
        fresh.offered,
        # The same two settings `announce` was given at startup, so the two
        # lines cannot disagree about facts a switch does not change (#56).
        overridden=settings.debug_max_context is not None,
        web=settings.web_enabled,
    )
    # AC 10, and the one startup fact a switch can make stale: declarations
    # follow the model, so moving to one that cannot call tools drops the real
    # cost to nothing while the figure from startup would stand.
    terminal.note_tool_cost(_tool_cost(fresh, settings), fresh.context)
    return fresh


def _limits(settings: config.Settings) -> "tools.Limits":
    """The bounds tools act within, built from the run's settings.

    One function because two callers need it: the chat loop, which hands it to
    every tool, and `_tool_cost`, which needs the standing prompt built from
    the same bounds. Building it twice would let the prompt a cost is measured
    from drift from the prompt actually sent.
    """
    return tools.Limits(
        working_directory=settings.working_directory,
        command_timeout=settings.command_timeout,
        search_results=settings.search_results,
        fetch_timeout=settings.fetch_timeout,
        page_characters=settings.page_characters,
    )


def _tool_cost(run: Running, settings: config.Settings) -> int | None:
    """What rides in every request before the conversation starts. None if nothing does.

    The declarations **and the standing prompt**. The prompt is the easy one to
    forget: it is held outside `messages` on purpose, so it does not look like
    part of the conversation, and it is roughly a fifth of the total. A figure
    without it understates what the user has actually spent.

    Weighed with `compaction.estimated_tokens` - the same function the size
    checks use - so this line cannot disagree with the behaviour it describes.
    That matters more than accuracy: `estimated_tokens` divides by four and
    `too_large` by three, and this prompt has been quoted at 56, then 163,
    before being measured at 205 by a third route (#43). A better number that
    contradicts the compaction it is explaining would be worse than none.

    None when there is nothing declared - tools off, or a model that cannot
    call them - so the caller stays silent rather than reporting a cost of
    zero, which is a number and reads like one.
    """
    if not run.declarations:
        return None
    return compaction.estimated_tokens(
        [
            *(
                {"role": "system", "content": json.dumps(declaration)}
                for declaration in run.declarations
            ),
            {"role": "system", "content": tools.system_prompt(_limits(settings))},
        ]
    )


def _remember(chosen: str, host: str) -> None:
    """Save the pick, and say so the first time a file is written here.

    The condition is the **file**, not the folder it goes in. #48 AC 30 asked
    about the folder and this asked about the folder to match - which meant any
    project that configures MCP, and so already has `.axiom/mcp.json`, got
    `model.json` written into it silently on that run and every run after. The
    criterion existed to stop something appearing in a user's project
    unannounced, and it let exactly that through one level down.

    Existence decides, deliberately, rather than anything remembered. A flag
    saying "already said" is true within a run and forgotten between them, so
    the next run would announce again - and deleting the file would not bring
    the announcement back, which is the behaviour a user would expect.
    """
    fresh = not models.DEFAULT_CHOICE_FILE.exists()
    problem = models.write_choice(chosen, host)
    terminal.note_choice_saved(
        problem, str(models.DEFAULT_CHOICE_FILE) if fresh and not problem else ""
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

    run = _prepare(model_backend, settings, attached, model)
    limits = _limits(settings)

    terminal.announce(
        run.model,
        settings.host,
        run.context,
        overridden=settings.debug_max_context is not None,
        tools=run.offered,
        web=settings.web_enabled,
    )
    terminal.note_servers(
        attached.connected,
        [*settings.mcp_problems, *attached.failures],
        bounds=(settings.mcp_start_timeout, settings.mcp_call_timeout),
    )
    # After the server lines rather than inside them. The figure is a fact
    # about the session - what rides in every request before a word is typed -
    # and it lived inside `note_servers`, which returns early when nothing is
    # attached. So a user with no MCP was told `7 tools including web` and
    # never that those seven were eating 40% of a small window (#61).
    #
    # Last of the startup lines, deliberately: the server counts above explain
    # where part of it comes from, so the total reads as their sum.
    terminal.note_tool_cost(_tool_cost(run, settings), run.context)

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
    # Empty until something schedules a job, and an empty one costs nothing:
    # `_next_line` takes the blocking read while it is empty. It lives here
    # rather than at module level so it dies with the session, which is AC 23.
    jobs = schedule.Schedule()

    while True:
        line, from_a_schedule = _next_line(jobs)
        if line is None or line in EXIT_COMMANDS:
            return
        if not line:
            continue

        if line == MODEL_COMMAND or line.startswith(MODEL_COMMAND + " "):
            switched = _switch_model(
                model_backend,
                settings,
                attached,
                run,
                line[len(MODEL_COMMAND) :].strip(),
            )
            if switched is _LEAVING:
                return
            if switched is not None:
                run = switched
                # The previous turn's count came from a different model's
                # tokenizer and is about to be weighed against a different
                # window. `None` is what a first turn already carries, and
                # `maybe_compact` handles it - the measured `too_large` check
                # still runs, so nothing is left unguarded.
                running_usage = None
            continue

        # The user did not type this one, and would otherwise be reading an
        # answer to a question they cannot see (#74 AC 13). Before `start_turn`,
        # so the blank line falls between the announcement and the reply.
        if from_a_schedule:
            terminal.note_scheduled(line)

        # Past every command and every empty line, so a turn that never
        # happens leaves no stray gap behind (AC 7, AC 8).
        terminal.start_turn()

        messages, kept_pairs, forgotten = compaction.maybe_compact(
            model_backend, run.model, messages, running_usage, run.context
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
        over = compaction.too_large(to_send(messages), run.context)
        if over is not None and run.context is not None:
            cause = compaction.what_will_not_fit(
                line, run.context, len(instructions["content"])
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
                # #42 ended the session here, and was right to at the time:
                # nothing the user could type would fit, so repeating the line
                # at every prompt was the discovery it was trying to prevent.
                # `/model` changes that - the window is a property of the model
                # and there is now a way to change the model without losing the
                # conversation. So the session stays, and the message names the
                # model and the way out rather than only the wall (#49 AC 19).
                terminal.report_too_large(over, cause, run.model)
                del messages[before:]
                terminal.end_turn()
                continue

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
                run.model,
                messages,
                run.context,
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
            over = compaction.too_large(to_send(messages), run.context)

        if over is not None:
            terminal.report_too_large(
                over,
                compaction.what_will_not_fit(
                    line, run.context, len(instructions["content"])
                ),
            )
            del messages[before:]
            terminal.end_turn()
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
                withholding = run.declarations is not None
                for event in model_backend.stream(
                    run.model, to_send(messages), run.options, run.declarations
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
                    announced = backend.call_from_text(reply, run.callable_names)
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
                        result = tools.run(call.name, call.arguments, limits, jobs)
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
            terminal.end_turn()
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
        terminal.end_turn()

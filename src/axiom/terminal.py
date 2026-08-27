"""Everything the user sees and types.

The only module under src/ that calls print() or input(). The chat loop asks
this module to say things rather than saying them itself, which is what keeps
one module from both talking to a backend and writing to a terminal.
"""

import sys

from .backend import ConnectionLost


def _accept_any_character(stream) -> None:
    """Windows consoles default to cp1252, and models emit emoji.

    Without this a single emoji in a reply kills the program mid-sentence with
    a UnicodeEncodeError - the model said something the console could not spell.
    Replacing the character is the right trade: an unreadable glyph beats a
    traceback over a finished answer.
    """
    try:
        stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        # Already replaced - under pytest, or a stream that cannot be retuned.
        pass


_accept_any_character(sys.stdout)
_accept_any_character(sys.stderr)

PROMPT = "> "
VOICE = "axiom:"  # how axiom identifies its own lines, as opposed to the model's


def show_models(
    models: tuple[str, ...], host: str, marked: str | None, current: bool = False
) -> None:
    """The installed models, numbered, with one marked.

    The same list at startup and at a switch - same contents, same order, same
    numbering (#49 AC 2), which is why both callers come here rather than each
    building one. Only the marker's wording differs: at startup it names what a
    bare enter accepts, and at a switch it names the model already in use,
    which enter keeps.

    The host is named with the list because the list is *about* that host: a
    model appearing to be missing is nearly always a run pointed somewhere the
    user did not mean, and the answer is on screen rather than in a flag they
    have to remember typing.

    Numbers are right-aligned so a ten-model host does not stagger the names.
    """
    print(f"{VOICE} models on {host}")
    width = len(str(len(models)))
    label = "  (current)" if current else "  (default)"
    for number, model in enumerate(models, start=1):
        print(f"  {number:>{width}}. {model}{label if model == marked else ''}")


def ask_model(hint: str = "enter for the default") -> str:
    """The user's answer to the list. Raises rather than swallowing.

    `EOFError` and `KeyboardInterrupt` reach the caller deliberately, because
    the two callers want different things from them. At startup both mean
    leave - there is no session to return to. Mid-conversation Ctrl-C means
    "never mind" and Ctrl-D means input has genuinely ended, and a single
    `None` for both could not tell them apart (#49 AC 26, AC 33).

    The blank line on the way out is printed here either way: the user pressed
    a key mid-line, and the next thing printed would otherwise land on it.
    """
    try:
        return input(f"{VOICE} which model? ({hint}) ")
    except (EOFError, KeyboardInterrupt):
        print()
        raise


def refuse_model(answer: str, count: int) -> None:
    """Why that answer did not name a model, said so the next try can work.

    Two refusals, because there are two ways to get it wrong once an empty
    line always works: a number out of range gets the range, and anything that
    is not a number gets told that numbers are what this wants. Both name the
    range, so the next attempt has what it needs without scrolling back.
    """
    given = answer.strip()
    if given.isdigit():
        print(
            f"{VOICE} there is no model {given} - type a number from 1 to {count}",
            file=sys.stderr,
        )
    else:
        print(
            f"{VOICE} {given!r} is not a number - type a number from 1 to {count}",
            file=sys.stderr,
        )


def note_model_missing(model: str, host: str) -> None:
    """A named model the host does not have.

    Said before anything else, and it never ends the run: what follows is the
    ordinary no-model-named path. Naming both halves matters - a model missing
    from the host the user meant is a different problem from a model missing
    because the run is pointed at the wrong host.
    """
    print(f"{VOICE} {model} is not installed on {host}", file=sys.stderr)


def note_choice_forgotten(model: str, host: str) -> None:
    """The remembered choice has been removed from the host since it was made."""
    print(
        f"{VOICE} {model} was your last choice here but {host} no longer has it",
        file=sys.stderr,
    )


def note_choice_unreadable(path: str) -> None:
    """The remembered choice exists but cannot be used.

    Its own sentence, and not `note_choice_forgotten`'s. The two are different
    facts with different fixes: a model the host dropped is the host's news and
    nothing is wrong locally, while this is a file the user can open and repair.
    Naming the path is the whole value - without it there is nothing to act on.

    Said rather than swallowed because the alternative is a user who edits the
    file, sees no effect, and has no way to learn why.
    """
    print(
        f"{VOICE} {path} could not be read - carrying on as though nothing "
        f"had been chosen here",
        file=sys.stderr,
    )


def note_settled(model: str, reason: str) -> None:
    """A model settled without asking, and why.

    Only for the routes that did not ask. A named model needs no explanation -
    the user typed it - so `named` says nothing and the startup line carries
    it. The other two are axiom choosing on the user's behalf, and AC 22 is
    that this never happens invisibly.
    """
    if reason == "only":
        print(f"{VOICE} using {model} - the only model installed")
    elif reason == "remembered":
        print(f"{VOICE} using {model} - your last choice here")
    elif reason == "first":
        print(f"{VOICE} using {model} - first installed, nothing was chosen")


def note_choice_saved(problem: str | None, path: str) -> None:
    """Said only when remembering failed, or when the folder is new.

    A successful save into a folder that already existed is silent - the user
    picked a model and got it, and a line confirming a file was written is
    noise. A *new* folder is different: axiom has just created something in a
    directory that is very often a git repository, and finding it later in
    `git status` with no idea what made it is worse than one line now.
    """
    if problem:
        print(f"{VOICE} {problem} - it will be asked again next time", file=sys.stderr)
    elif path:
        print(f"{VOICE} remembering this choice in {path}")


def note_switched(model: str, context: int | None, tools: int | None) -> None:
    """What changed, said the moment it changes.

    The window and the tool count are named because they are the two things a
    switch silently alters underneath a conversation that is already running -
    and both can shrink. A user who moves to a smaller model and is not told
    the window shrank will read the next compaction as axiom losing its place.
    """
    room = "Ollama default" if context is None else f"{context} tokens"
    if tools is None:
        can_do = "no tools - this model cannot call them"
    elif tools == 0:
        can_do = "tools off"
    else:
        can_do = f"{tools} tools"
    print(f"{VOICE} now {model} (context: {room}, {can_do})")


def note_unchanged(model: str) -> None:
    """Nothing happened, said so the silence is not mistaken for a switch."""
    print(f"{VOICE} still {model}")


def note_only_model(model: str) -> None:
    """There is nothing to switch to, and the list would say nothing useful."""
    print(f"{VOICE} {model} is the only model installed - nothing to switch to")


def report_switch_failed(host: str, cause: BaseException, model: str) -> None:
    """The host could not be listed, and the session is carrying on regardless.

    Says which model it is carrying on with, because the user asked to change
    it and is entitled to know they did not. Not fatal, unlike the same failure
    at startup: there is a working session and a working model here, and losing
    the list is a reason to stay put rather than to end it.
    """
    print(
        f"{VOICE} cannot reach Ollama at {host} ({cause}) - staying on {model}",
        file=sys.stderr,
    )


def refuse_command(form: str) -> None:
    """A command that was recognised but not usable as typed."""
    print(f"{VOICE} {form}", file=sys.stderr)


def report_no_models(host: str) -> None:
    """The host answered and has nothing to offer."""
    print(
        f"error: {host} has no models installed - pull one first, for example "
        f"`ollama pull qwen2.5:7b`",
        file=sys.stderr,
    )


def report_no_host(host: str, cause: BaseException) -> None:
    """The host could not be asked at all.

    Distinct from having no models, because the advice differs and the user
    can act on exactly one of them. Reaching this means nothing was printed
    that could be read as a list or a reply.
    """
    print(f"error: cannot reach Ollama at {host} ({cause})", file=sys.stderr)


def announce(
    model: str,
    host: str,
    context: int | None,
    overridden: bool,
    tools: int | None,
    web: bool = False,
) -> None:
    """The startup line: what we are talking to, with how much room, and what
    it can do.

    `tools` is how many are available, 0 when the user switched them off, and
    None when the model cannot call them at all. The three read differently
    because the user can act on them differently - one is their own choice,
    one is a fact about the model.

    `web` only means anything when tools are available, which is what keeps
    two three-state settings from becoming nine sentences: with no tools there
    is nothing to say about the web, and the line stays one line.
    """
    if context is None:
        room = "Ollama default"
    else:
        room = f"{context} tokens{', debug override' if overridden else ''}"

    if tools is None:
        can_do = "no tools - this model cannot call them"
    elif tools == 0:
        can_do = "tools off"
    elif web:
        can_do = f"{tools} tools including web"
    else:
        can_do = f"{tools} tools, web off"

    print(f"{VOICE} {model} at {host} (context: {room}, {can_do})")


def note_starting(servers: int) -> None:
    """Said before the wait, because starting a server can take seconds.

    A silent pause before the first prompt reads as a hang, and the user has no
    way to tell one from the other.
    """
    if servers:
        word = "server" if servers == 1 else "servers"
        print(f"{VOICE} starting {servers} MCP {word}...")


def note_servers(
    connected: dict[str, int],
    problems: list[str],
    bounds: tuple[float, float] | None = None,
    cost: int | None = None,
    window: int | None = None,
) -> None:
    """Which MCP servers answered, what went wrong, and what it all costs.

    Said after the startup line and only when there is something to say, so a
    run with nothing configured looks exactly as it did before MCP existed.

    Problems are named one by one rather than counted: each is fixed by a
    different action - setting a variable, correcting a command, removing a
    tool that does not exist - and a count says none of that.

    `cost` is what the declared tools take out of the window before a
    conversation has started. Tool declarations ride in every request, the way
    #42 measured the system prompt at 205 tokens, so a server contributing
    twenty is a fixed tax the user would otherwise never see.
    """
    if not connected and not problems:
        return

    for name, count in connected.items():
        tools_word = "tool" if count == 1 else "tools"
        print(f"{VOICE} {name}: {count} {tools_word}")

    if connected and cost is not None:
        share = f", {100 * cost / window:.0f}% of the window" if window else ""
        print(f"{VOICE} tools cost about {cost} tokens per request{share}")
    if connected and bounds is not None:
        start, call = bounds
        print(f"{VOICE} server start limit {start:g}s, tool call limit {call:g}s")

    for problem in problems:
        print(f"{VOICE} {problem}", file=sys.stderr)


def read_line() -> str | None:
    """The next line the user types, or None if they are leaving."""
    try:
        return input(PROMPT).strip()
    except (EOFError, KeyboardInterrupt):
        # Ctrl-C at an idle prompt means leave, same as Ctrl-D.
        print()
        return None


def show_piece(text: str) -> None:
    print(text, end="", flush=True)


def end_reply() -> None:
    print()


TOOL_OUTPUT_LIMIT = 2000


def note_tool(name: str, arguments: dict, outside: list[str] | None = None) -> None:
    """What is about to run, before it runs.

    Values are shown as they are, not repr'd: a Windows path through repr()
    comes out with every backslash doubled, which is not what the user typed
    and not what they would type to check it.

    `outside` names paths that land outside the working directory, resolved
    (#41 AC 6). Shown on its own line rather than folded into the arguments,
    because `path=notes.txt` is what the model asked for and where that
    actually lands is a different fact. Visibility only - nothing is blocked.
    """
    if isinstance(arguments, dict):
        detail = ", ".join(f"{key}={value}" for key, value in arguments.items())
    else:
        # A call announced as text can carry anything at all. Show it as it
        # came - running it is what reports that it cannot be used.
        detail = str(arguments)
    print(f"{VOICE} {name}({detail})")
    for path in outside or []:
        print(f"{VOICE} outside the working directory: {path}")


def note_round_limit(rounds: int) -> None:
    """The turn ended because it ran out of rounds, not because it answered.

    Without this the user gets whatever `reply` happened to hold, which after
    a turn that called tools every round is nothing at all (#41 AC 10).
    """
    print(
        f"{VOICE} stopped after {rounds} rounds of tool calls without an answer. "
        f"Nothing further was tried."
    )


def show_tool_result(result: str) -> None:
    """A tool's output, marked so it cannot be read as the model's answer."""
    shown = result[:TOOL_OUTPUT_LIMIT]
    for line in shown.splitlines() or [""]:
        print(f"  | {line}")
    withheld = len(result) - len(shown)
    if withheld:
        print(f"  | ... {withheld} more characters not shown")


def show_sources(read: list[str], seen: list[str]) -> None:
    """Which addresses axiom actually retrieved, in axiom's own voice.

    Deliberately not the model's citations. Asked to cite, a small model will
    invent a plausible address it never read; told not to, it names none at
    all. These two lists are what was really fetched and really returned, so
    they are worth trusting - and the VOICE prefix is what tells the reader
    which lines are axiom's rather than the model's.

    Read and merely seen are kept apart because they are different claims. A
    page that was fetched is a source; an address that appeared in results is
    not, and presenting one as the other is the thing this exists to prevent.
    """
    if read:
        print(f"{VOICE} read: " + ", ".join(read))
    only_seen = [address for address in seen if address not in read]
    if only_seen:
        print(f"{VOICE} found, not read: " + ", ".join(only_seen))


def note_compaction(kept_pairs: int) -> None:
    level = "everything" if kept_pairs == 0 else f"keeping the last {kept_pairs}"
    print(f"{VOICE} compacting older history ({level})")


def note_facts_forgotten(dropped: list[str]) -> None:
    """Said when the summary reached its bound and the oldest facts were let go.

    Named one by one rather than counted. #32 asks that a long session never
    *silently* loses information - not that it never loses any, which is not
    arithmetically available - and a count tells the user something went
    without telling them whether it mattered. Seeing it is what lets them say
    it again if it did.
    """
    print(f"{VOICE} the summary is full - forgetting {len(dropped)}:")
    for fact in dropped:
        print(f"  | {fact}")


def report_too_large(over: int, cause: str = "message", model: str = "") -> None:
    """Said instead of sending a payload that would not fit.

    Three causes, three messages, because #42 AC 5 asks that the user be told
    what is *actually* too large and suggested only something that would help.
    One message for all three was advice to type less in a case where typing
    less could never work: #42 cycle 1 watched the overage stop falling at 5
    tokens while the message shrank to a single character.

    `cause` comes from `compaction.what_will_not_fit`. Said after compaction
    has already had its turn, so none of these suggest waiting for one.
    """
    if cause == "cannot-continue":
        # #42 AC 6 asked that the user hear this once and that the session end,
        # because nothing they typed could work and repeating an unhelpable
        # line at every prompt *is* discovery-by-retrying.
        #
        # #49 AC 19 makes it helpable. The window belongs to the model, and
        # `/model` moves to another without losing the conversation - so the
        # line names the model that cannot hold it and the way out, and the
        # session stays. It may now repeat, and that is the right trade: a
        # repeated line carrying an action beats one refusal and a closed
        # session with the conversation gone.
        cannot = f"{model} cannot" if model else "this session cannot"
        print(
            f"error: {cannot} hold even an empty message - the context is too "
            f"small, so nothing you type will fit. Use /model to switch to a "
            f"model with a larger context, or restart axiom with one.",
            file=sys.stderr,
        )
    elif cause == "conversation":
        # Currently unreachable through `main()`, and deliberately kept.
        #
        # #42 cycle 4 added a last resort: when nothing on the ladder fits, the
        # summary is let go and the session carries on. Its guard is exactly
        # this case's condition, so wherever the conversation would have been
        # the blocker the session is rescued instead of refused. Swept 35
        # context/message-size combinations and only "message" was ever
        # reached.
        #
        # Kept because AC 5 names the conversation as something this should be
        # able to say, and because the alternative is that a later change to
        # that guard has no message for the case at all.
        print(
            f"error: the conversation so far is about {over} tokens too large "
            f"to send, and it has already been compacted as far as it goes - "
            f"start a new session to carry on",
            file=sys.stderr,
        )
    else:
        print(
            f"error: this message is about {over} tokens too large to send - "
            f"try a shorter one",
            file=sys.stderr,
        )


def report_truncated(estimated: int, seen: int) -> None:
    """Said when the model evidently answered from a prompt it never fully saw.

    There is no error to report from the model's side - it accepts the oversized
    prompt, cuts it, and answers confidently. Without this the user reads a
    reply built on a fragment as though it were built on everything.
    """
    print(
        f"error: the model saw about {seen} tokens of roughly {estimated} sent - "
        f"the reply above is built on a truncated conversation",
        file=sys.stderr,
    )


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
    elif isinstance(failure, ConnectionLost) and reply:
        # Part of a reply is already on screen. Say so, or the user reads a
        # fragment as though it were the whole answer.
        message = (
            f"error: reply cut off after {len(reply)} characters "
            f"- lost connection to {host} ({failure})"
        )
    elif isinstance(failure, ConnectionLost):
        message = f"error: cannot reach Ollama at {host} ({failure})"
    else:
        message = f"error: {failure}"

    if reply or isinstance(failure, KeyboardInterrupt):
        print(file=sys.stderr)
    print(message, file=sys.stderr)

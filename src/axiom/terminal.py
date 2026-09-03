"""Everything the user sees and types.

The only module under src/ that calls print() or input(). The chat loop asks
this module to say things rather than saying them itself, which is what keeps
one module from both talking to a backend and writing to a terminal.
"""

import os
import queue
import re
import sys
import threading

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


def say(message: str, stream=None) -> None:
    """One line in axiom's own voice (#77 AC 27, AC 28).

    At a terminal: a grey `·` and a grey line. Everywhere else: `axiom: message`,
    exactly the bytes this module printed before #77 - which is what keeps the
    golden transcript still and AC 33 and AC 35 true.

    **Why the marker rather than the name.** The prefix was on every line axiom
    said, so the eye had to read each one to find out whose it was; a name
    repeated forty times identifies nothing. The grey does that job without a
    word, and the `·` marks the line as axiom's for anyone reading a transcript
    where colour has been stripped.

    **Why the whole line and not just the marker.** AC 27 is that axiom's own
    output is *dimmer than the answer*. A grey bullet in front of a full-strength
    sentence leaves the sentence competing with the model's reply, which is the
    complaint this came from.

    The gate is the stream being written to, not stdout: a run with stdout piped
    and stderr still at the terminal should not have its errors decided by where
    the answer went.
    """
    print(_voiced(message, stream), file=stream if stream is not None else sys.stdout)


def _voiced(message: str, stream=None) -> str:
    """One line in axiom's voice, as a string rather than printed.

    For the places that cannot use `say`: a question, whose cursor has to land
    after it rather than on the row below, and anything that has to measure the
    line before writing it.

    Assembled rather than interpolated on the plain path, deliberately. This is
    the one place `VOICE` is still spelled out, and an f-string opening with it
    would make this function look like all the others to anything scanning for
    them - including the pass that converted them, which would have turned this
    line into a call to itself.
    """
    stream = stream if stream is not None else sys.stdout
    if not _rendering or not stream.isatty():
        return VOICE + " " + message
    return _grey("·  " + message)


def show_models(
    models: tuple[str, ...],
    host: str,
    marked: str | None,
    current: bool = False,
    capable: set[str] | None = None,
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

    Numbers are right-aligned so a ten-model host does not stagger the names,
    and names are padded to the longest so the annotations line up under each
    other rather than staggering with them (#77 AC 2).
    """
    number_width = len(str(len(models)))
    longest = max((len(model) for model in models), default=0)
    label = "  (current)" if current else "  (default)"
    # Annotated only where it explains something (#52 AC 8): a host whose
    # models can *all* call tools, or none of which can, has an order that is
    # plain name order, and a note on every row would explain nothing while
    # making every row longer. Mixed hosts are the case the ordering exists
    # for, and the only case where a reader needs to be told why.
    mixed = capable is not None and 0 < len(capable) < len(models)

    rows = []
    for number, model in enumerate(models, start=1):
        marked_here = model == marked
        # Padded even on the last column's absence: a row with no annotation
        # still holds the name's column open, or the marker below it moves.
        name = model.ljust(longest) if mixed or marked_here else model
        tools = "  tools" if mixed and model in capable else ("      " if mixed else "")
        rows.append(
            (f"{number:>{number_width}}. ", name, tools, label if marked_here else "")
        )
    _show_model_panel(rows, host)

    if capable is not None and not capable:
        # AC 9. Said once rather than per row - it is a fact about the host,
        # not about any one model, and without it the order looks arbitrary.
        say("none of these can call tools")


def _show_model_panel(rows: list[tuple[str, str, str, str]], host: str) -> None:
    """The numbered list, inside a border, in the accent (#77 AC 1).

    A rendering failure must not cost the user the list - the same promise
    `_as_markdown` makes about a reply. Without the fallback a Rich that cannot
    draw a box would leave a user who has to choose a model with nothing to
    choose from.
    """
    try:
        from rich.box import ROUNDED
        from rich.console import Console
        from rich.panel import Panel
        from rich.text import Text

        body = Text()
        for index, (number, name, tools, marker) in enumerate(rows):
            if index:
                body.append("\n")
            body.append(number, style=ACCENT)
            body.append(name, style=f"bold {ACCENT}" if marker else "")
            # "dim default" rather than "dim": a style inside a panel is laid
            # over the border's, so a bare "dim" inherits the accent and comes
            # out tinted rather than grey.
            body.append(tools, style="dim default")
            body.append(marker, style=f"bold {ACCENT}")

        Console(
            force_terminal=sys.stdout.isatty(),
            legacy_windows=False,
            no_color=_colourless(),
            width=_width(),
        ).print(
            Panel(
                body,
                # **The whole phrase, not a `models` title with the host as a
                # subtitle.** Ten assertions across test_models, test_switch and
                # test_tools_first match `models on <host>`, and four of them are
                # negatives - `assert "models on" not in out.out`. Shortening this
                # title does not fail them, it makes them **pass while testing
                # nothing**. Keep the phrase whole.
                title=Text(f"models on {host}", style=f"bold {ACCENT}"),
                title_align="left",
                border_style=ACCENT,
                box=ROUNDED,
                padding=(1, 2),
                expand=False,
            )
        )
    except Exception:
        # The same trade `_as_markdown` makes: formatting is what a failure
        # costs, never the content.
        say(f"models on {host}")
        for number, name, tools, marker in rows:
            print(f"  {number}{name.rstrip()}{tools}{marker}")


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
        # `say` cannot be used here: this is a question, and the cursor has to
        # land after it rather than on the row below. So it takes the same two
        # forms by hand - `axiom: which model?` when nothing is being drawn, and
        # a grey marked line at a terminal (#77 AC 27, AC 28).
        return input(_voiced(f"which model? ({hint}) "))
    except (EOFError, KeyboardInterrupt):
        print()
        raise


def refuse_model(answer: str, count: int, names: bool = False) -> None:
    """Why that answer did not name a model, said so the next try can work.

    Two refusals, because there are two ways to get it wrong once an empty
    line always works: a number out of range gets the range, and anything that
    is not a number gets told what this wants. Both name the range, so the
    next attempt has what it needs without scrolling back.

    `names` widens the advice where a name is also accepted - the switch list
    takes either, and telling a user there only that a number is wanted would
    be advice that is narrower than the truth.
    """
    given = answer.strip()
    wanted = (
        f"type a number from 1 to {count}, or a model's full name"
        if names
        else f"type a number from 1 to {count}"
    )
    if given.isdigit():
        say(f"there is no model {given} - {wanted}", sys.stderr)
    else:
        say(f"{given!r} is not a number - {wanted}", sys.stderr)


def note_model_missing(model: str, host: str) -> None:
    """A named model the host does not have.

    Said before anything else, and it never ends the run: what follows is the
    ordinary no-model-named path. Naming both halves matters - a model missing
    from the host the user meant is a different problem from a model missing
    because the run is pointed at the wrong host.
    """
    say(f"{model} is not installed on {host}", sys.stderr)


def note_choice_forgotten(model: str, host: str) -> None:
    """The remembered choice has been removed from the host since it was made."""
    say(
        f"{model} was your last choice here but {host} no longer has it",
        sys.stderr,
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
    say(
        f"{path} could not be read - carrying on as though nothing "
        f"had been chosen here",
        sys.stderr,
    )


def settled_because(reason: str) -> str | None:
    """Why axiom chose this model, in words, or None if the user chose it.

    One function because the phrase is now said in two places - the line below
    and the facts panel's model row (#77 AC 15) - and two copies of a sentence
    are two sentences the moment one of them is edited.
    """
    return {
        "only": "the only model installed",
        "remembered": "your last choice here",
        "first": "first installed, nothing was chosen",
    }.get(reason)


def note_settled(model: str, reason: str) -> None:
    """A model settled without asking, and why.

    Only for the routes that did not ask. A named model needs no explanation -
    the user typed it - so `named` says nothing and the startup line carries
    it. The other two are axiom choosing on the user's behalf, and AC 22 is
    that this never happens invisibly.
    """
    because = settled_because(reason)
    if because:
        say(f"using {model} - {because}")


def note_choice_saved(problem: str | None, path: str) -> None:
    """Said only when remembering failed, or when the file is new.

    A save over a file that was already there is silent - the user picked a
    model and got it, and a line confirming a write they have seen before is
    noise. A *new file* is different: axiom has just put something in a
    directory that is very often a git repository, and finding it later in
    `git status` with no idea what made it is worse than one line now.

    The caller decides which case this is, and decides it by whether the file
    existed - not the folder. Asking about the folder meant a project that
    already had `.axiom/mcp.json` was never told at all.

    `path` empty means silence, so a failed save reports the failure and never
    also claims a file was written.
    """
    if problem:
        say(f"{problem} - it will be asked again next time", sys.stderr)
    elif path:
        say(f"remembering this choice in {path}")


def note_switched(
    model: str,
    context: int | None,
    tools: int | None,
    overridden: bool,
    web: bool,
) -> None:
    """What changed, said the moment it changes.

    The window and the tool count are named because they are the two things a
    switch silently alters underneath a conversation that is already running -
    and both can shrink. A user who moves to a smaller model and is not told
    the window shrank will read the next compaction as axiom losing its place.

    It carries **every fact the startup line carries** that a switch does not
    make stale, and it says each in the same words, because it builds them with
    the same two functions. It used to build its own, and two facts were
    missing: the web state, so `--no-web` was unknowable from the line after a
    switch; and the override note, so a forced window read as the model's own.

    The host is the one thing deliberately left out. A switch cannot change it
    and the startup line already named it (#56 AC 11).

    `overridden` and `web` have **no defaults**, deliberately. A default would
    let a caller omit a fact and still produce a plausible-looking line - which
    is exactly the defect this function had. Worse, `False` is the *right*
    answer often enough to hide it: the cold read found three tests passing
    against a deliberately broken caller purely because the default happened to
    match. Required arguments turn that silence into a `TypeError`.
    """
    say(f"now {model} (context: {_room(context, overridden)}, {_can_do(tools, web)})")


def note_unchanged(model: str) -> None:
    """Nothing happened, said so the silence is not mistaken for a switch."""
    say(f"still {model}")


def note_current_missing(model: str, host: str) -> None:
    """The model in use is no longer on the host, and is still in use.

    Said because it cannot be shown: the list holds what the host reports and
    nothing else, so a model that has been removed has no row to be marked in.
    Without this the list appears with nothing marked and the user has no way
    to tell what they are currently talking to (#49 AC 31).

    The session is unaffected - Ollama has the model loaded or will load it
    from what it still has; being absent from `/api/tags` is not the same as
    being unusable this second, and guessing otherwise would end a working
    conversation over a listing.
    """
    say(
        f"still on {model}, which {host} no longer lists",
        sys.stderr,
    )


def note_only_model(model: str) -> None:
    """There is nothing to switch to, and the list would say nothing useful."""
    say(f"{model} is the only model installed - nothing to switch to")


def report_switch_failed(host: str, cause: BaseException, model: str) -> None:
    """The host could not be listed, and the session is carrying on regardless.

    Says which model it is carrying on with, because the user asked to change
    it and is entitled to know they did not. Not fatal, unlike the same failure
    at startup: there is a working session and a working model here, and losing
    the list is a reason to stay put rather than to end it.
    """
    say(
        f"cannot reach Ollama at {host} ({cause}) - staying on {model}",
        sys.stderr,
    )


def refuse_command(form: str) -> None:
    """A command that was recognised but not usable as typed."""
    say(f"{form}", sys.stderr)


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


def _room(context: int | None, overridden: bool) -> str:
    """How much room there is, in words.

    Shared by the startup line and the switch line, deliberately. The two used
    to phrase this independently, and the `debug override` note existed in one
    and not the other - so after a switch a forced window read as the model's
    own, which is the exact number someone debugging a compaction problem
    reasons from (#56 AC 2, AC 9).

    One function means they cannot say it differently for the same state,
    whatever either is later changed to say.
    """
    if context is None:
        return "Ollama default"
    return f"{context} tokens{', debug override' if overridden else ''}"


def _can_do(tools: int | None, web: bool) -> str:
    """What the model can reach, in words. Shared for the same reason as `_room`.

    `tools` is how many are available, 0 when the user switched them off, and
    None when the model cannot call them at all. The three read differently
    because the user can act on them differently - one is their own choice,
    one is a fact about the model.

    `web` only means anything when tools are available, which is what keeps two
    three-state settings from becoming nine sentences: with no tools there is
    nothing to say about the web, and the line stays one line.
    """
    if tools is None:
        return "no tools - this model cannot call them"
    if tools == 0:
        return "tools off"
    return f"{tools} tools including web" if web else f"{tools} tools, web off"


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
    say(
        f"{model} at {host} "
        f"(context: {_room(context, overridden)}, {_can_do(tools, web)})"
    )


def note_starting(servers: int) -> None:
    """Said before the wait, because starting a server can take seconds.

    A silent pause before the first prompt reads as a hang, and the user has no
    way to tell one from the other.
    """
    if servers:
        word = "server" if servers == 1 else "servers"
        say(f"starting {servers} MCP {word}...")


def note_tool_cost(cost: int | None, window: int | None) -> None:
    """What the declared tools take out of the window before anything is said.

    Its own saying, not part of the server report. It used to live inside
    `note_servers`, which returns early when nothing is attached - so this,
    which is a fact about the *session*, was shown only to users who happened
    to configure MCP. Everyone else was told `7 tools including web` and never
    that those seven cost 653 tokens, or that with the standing prompt they
    took 40% of a 2000-token window before a word was typed (#61).

    `cost` is None when nothing is declared, and the line is then not said at
    all. Deliberately not a cost of zero: zero is a number, it reads like one,
    and a user who has switched tools off does not need to be told what they
    are not paying.

    The share is omitted rather than guessed when the window is unknown - a
    percentage of an unknown is not a smaller claim, it is a wrong one.
    """
    if cost is None:
        return
    share = f", {100 * cost / window:.0f}% of the window" if window else ""
    say(f"tools cost about {cost} tokens per request{share}")


def note_servers(
    connected: dict[str, int],
    problems: list[str],
    bounds: tuple[float, float] | None = None,
) -> None:
    """Which MCP servers answered, and what went wrong.

    Said after the startup line and only when there is something to say, so a
    run with nothing configured looks exactly as it did before MCP existed.

    Problems are named one by one rather than counted: each is fixed by a
    different action - setting a variable, correcting a command, removing a
    tool that does not exist - and a count says none of that.

    What the tools *cost* is no longer said here. It never belonged: it is a
    fact about every request, servers or not, and living inside a function that
    returns early without them is what kept it hidden (#61).
    """
    if not connected and not problems:
        return

    for name, count in connected.items():
        tools_word = "tool" if count == 1 else "tools"
        say(f"{name}: {count} {tools_word}")

    if connected and bounds is not None:
        start, call = bounds
        say(f"server start limit {start:g}s, tool call limit {call:g}s")

    for problem in problems:
        say(f"{problem}", sys.stderr)


WAITING = object()
"""Nothing was typed before the timeout ran out. Not a line, and not leaving."""


class Typed:
    """The user's lines, read on a thread so the loop can watch a clock too.

    `input()` blocks until a newline arrives, and that is where a session spends
    nearly all of its life. A schedule cannot fire from inside it: a user idle at
    the prompt at 08:59 would get their 09:00 job whenever they next pressed
    enter, which might be tomorrow (#74 AC 9).

    Reading on a thread and handing lines over a queue lets the main loop wait
    with a timeout and look at the clock each time one runs out. **Turn execution
    stays on the main thread** - this thread only ever reads - so a job still
    cannot begin while a turn is in progress, and two jobs still cannot overlap.
    AC 10 and AC 11 keep holding for the same reason they did before: there is
    one place that runs a turn, and it runs one at a time.
    """

    def __init__(self, read=None) -> None:
        # `input()` with no prompt string, deliberately. The prompt belongs to
        # the caller, not to the read - see `show_prompt`. A thread that drew it
        # would draw it at a moment the main loop cannot predict, and a job
        # firing would then have to reach into another thread's output.
        self._read = read or (lambda: input())
        # One line at a time. `put` blocks until the caller has taken the last
        # one, so the thread reads exactly as fast as the loop consumes.
        #
        # Unbounded, this spins: a reader that returns without blocking - which
        # a real `input()` never does, and a test's fake always does - fills the
        # queue as fast as the interpreter allows. Found by the wall clock, not
        # by a failing test: fourteen tests taking 0.04s each, and the file
        # taking five seconds.
        #
        # Nothing is lost by the bound. A line the user has typed but that has
        # not been read yet is still sitting in the terminal's own buffer.
        self._lines: "queue.Queue[str | None]" = queue.Queue(maxsize=1)
        self._thread: "threading.Thread | None" = None

    def _pump(self) -> None:
        while True:
            try:
                line = self._read()
            except (EOFError, KeyboardInterrupt):
                # Ctrl-C and Ctrl-D at an idle prompt both mean leave. The
                # contract `read_line` has always had, carried across the queue.
                self._lines.put(None)
                return
            self._lines.put(line.strip())

    def next(self, timeout: float) -> "str | None | object":
        """A line, `None` for leaving, or `WAITING` if the timeout ran out.

        The thread starts on the first call rather than in `__init__`, so
        constructing one of these costs nothing and a session that never
        schedules anything never starts a thread at all.
        """
        if self._thread is None:
            self._thread = threading.Thread(target=self._pump, daemon=True)
            self._thread.start()
        try:
            return self._lines.get(timeout=timeout)
        except queue.Empty:
            return WAITING


_typed: "Typed | None" = None


def use_input(read=None) -> None:
    """Replace the reader behind the timed read, or forget the one in use.

    A module-level singleton is right for a program with one console and wrong
    for a test suite: without this, the first test to take a timed read leaves a
    thread reading a `builtins.input` that the next test has already replaced,
    and the failure shows up as flakiness somewhere unrelated.

    `None` forgets it, so the next timed read builds a fresh one.
    """
    global _typed
    _typed = Typed(read=read) if read is not None else None


def _compose_continuation():
    """What marks the second line of a message, and the third (#80 AC 23).

    prompt_toolkit's default is `prompt_width` spaces. That lines the text up
    and **marks nothing** - so a message part way through looks exactly like one
    that has already been sent and answered, which is the one thing AC 23 asks
    it not to look like.

    A marker in the voice's grey instead: quieter than the answer, because it is
    axiom's furniture rather than the user's words, and visible enough to say
    "still yours, not sent". Every line staying on screen is what AC 4 and AC 24
    ask for, and prompt_toolkit does that part already.

    Returned as a callable rather than inlined so it can be tested without a
    console. An inline lambda here would be an untested one.
    """
    from prompt_toolkit.formatted_text import ANSI

    def marker(width: int, line_number: int, wrapped: bool):
        return ANSI(_grey("…".ljust(max(1, width))))

    return marker


_said_how_to_send = False


def forget_the_hint() -> None:
    """Let the hint be said again. For tests, and for a new session."""
    global _said_how_to_send
    _said_how_to_send = False


def _say_how_to_send() -> None:
    """How to send, said the first time a message grows a second line (#80 AC 5).

    **Once per session, and that is the whole design.** A user who has just
    discovered ctrl+enter has also just discovered that enter no longer does what
    it did a moment ago, which is the one moment the answer is worth having. Said
    again on the second line it is noise, and by the fourth it is in the way of
    the thing being written.

    Printed above the prompt through `run_in_terminal`, because the reader owns
    the screen while it is running and writing underneath it would be drawn over.
    """
    global _said_how_to_send
    if _said_how_to_send:
        return
    _said_how_to_send = True
    from prompt_toolkit.application import run_in_terminal

    run_in_terminal(lambda: say("enter sends, ctrl+enter starts another line"))


def compose(source=None, sink=None) -> str:
    """A message, however many lines it has (#80 AC 1, AC 2, AC 3).

        enter        c-m            send it
        ctrl+enter   escape, c-j    start another line

    **`"c-enter"` is not a key, and binding it finds nothing.** On Windows
    ctrl+enter arrives as a line feed with the control state set, and
    prompt_toolkit turns that into escape-then-ControlJ - the VT100 convention
    for a meta-modified key. It maps carriage return to ControlM and line feed
    to ControlJ, then prefixes ControlJ with Escape when either control key is
    down. Read out of `prompt_toolkit/input/win32.py`; quoted in full in
    `.claude/loop/80-multiline/iteration-1/logs/cycle-1.md`.

    A consequence worth knowing rather than discovering: **ctrl+enter and
    ctrl+J are the same bytes to the console**, so they are the same key to
    anything reading it. Nothing can separate them. Ctrl+J is not otherwise
    used here, so the collision costs nothing - but it is a decision, not an
    accident.

    `multiline=True` is what lets the buffer hold a second line at all. With
    it, prompt_toolkit's own default is the opposite of this - enter inserts
    and escape-enter accepts - so both bindings are stated rather than one.

    `source` and `sink` exist for tests. prompt_toolkit's `create_pipe_input`
    delivers key presses without a terminal, which proves what axiom does with
    a key - **not** that this console delivers it. That second half is the
    manual pass's, and it is why AC 2 and AC 3 stay off the proved list.

    Imported here rather than at module scope: a piped run must not pay to
    load a library it never reaches.
    """
    from prompt_toolkit import PromptSession
    from prompt_toolkit.formatted_text import ANSI
    from prompt_toolkit.key_binding import KeyBindings

    keys = KeyBindings()

    @keys.add("c-m")
    def _send(event) -> None:
        event.current_buffer.validate_and_handle()

    @keys.add("escape", "c-j")
    def _newline(event) -> None:
        _say_how_to_send()
        event.current_buffer.insert_text("\n")

    @keys.add("c-c")
    def _abandon(event) -> None:
        """Throw the message away, or leave if there is nothing to throw.

        #80 AC 25, AC 26 - and the two pull against each other, which is why
        both are here rather than one.

        ctrl+c has always meant "leave" at an idle prompt, and that was right
        when a prompt held one line and nothing was ever in progress. With four
        lines half-written it is wrong: the user means *not that*, not goodbye,
        and ending the session would take the conversation with it.

        So it depends on whether there is anything to abandon. With text in the
        buffer it is cleared and the prompt stays; empty, the interrupt goes up
        exactly as it did before #80, and `read_line` ends the session.

        Nothing is sent either way, and nothing reaches the history - which is
        AC 27, and it is structural rather than defended: this returns to the
        reader, and only a message that is *accepted* leaves it.
        """
        if event.current_buffer.text:
            event.current_buffer.reset()
            return
        # No `style=` argument, deliberately. prompt_toolkit accepts one here
        # and the natural value is a class name of the form family-colon-tag -
        # which is also the shape of a model name, so `test_config`'s guard
        # against a default model creeping back reads it as one. The guard is
        # right, the styling is worth nothing, and widening the guard to suit a
        # cosmetic argument would be trading a real check for no gain.
        event.app.exit(exception=KeyboardInterrupt)

    session = PromptSession(
        multiline=True,
        key_bindings=keys,
        input=source,
        output=sink,
        prompt_continuation=_compose_continuation(),
    )
    # `ANSI(...)`, not the bare string: prompt_toolkit measures a prompt to
    # place the cursor, and escape sequences handed to it as text are counted as
    # visible columns and printed literally. #77 put the accent in there.
    return session.prompt(ANSI(_prompt()))


_compose = None


def use_compose(read=None) -> None:
    """Replace the reader that composes a message, or forget the one in use.

    The counterpart of `use_input`, and for the same reason it exists: a
    module-level singleton is right for a program with one console and wrong for
    a test suite.

    It is also **the only way #80 is testable at all.** Every other test in this
    suite supplies input by monkeypatching `builtins.input`, and a reader that
    only runs at a terminal is unreachable from all of them - no test process is
    a terminal. Without this hook the feature could be built and never checked,
    which is how #77 nearly shipped a panel nothing had looked at.

    `None` forgets it, so the next read goes back to the real one.
    """
    global _compose
    _compose = read


def _composer():
    """The composing reader, or None when this run should read a plain line.

    **Terminal-only, and that is load-bearing rather than tidy.** The golden
    transcript is 477 lines captured from a `StringIO` and every test drives
    axiom by feeding it lines; a composer reachable from a piped run changes all
    of that at once. Same split #77 landed on, for the same reason.
    """
    if not _rendering or not sys.stdout.isatty():
        return None
    return _compose or compose


def read_line(timeout: float | None = None) -> "str | None | object":
    """The next line the user types, or None if they are leaving.

    With no timeout this is exactly what it has always been - a blocking read on
    the calling thread. Every existing caller and every existing test takes this
    path, and none of them can tell that the other one exists.

    With a timeout it returns `WAITING` when nothing was typed in that time, so
    the caller can look at the clock and come back. That is the only way a
    scheduled prompt can run while the user sits at an idle prompt rather than
    after they next press enter.
    """
    if timeout is None:
        try:
            composer = _composer()
            return composer().strip() if composer else input(_prompt()).strip()
        except (EOFError, KeyboardInterrupt):
            # Ctrl-C at an idle prompt means leave, same as Ctrl-D.
            print()
            return None
    global _typed
    if _typed is None:
        _typed = Typed()
    got = _typed.next(timeout)
    if got is None:
        print()
    return got


def show_prompt() -> None:
    """Draw the prompt, for a caller reading with a timeout.

    The untimed `read_line` still draws its own, because `input(PROMPT)` is one
    call and every existing caller uses it. A timed read cannot: the read is on
    another thread, and a job firing has to take the prompt back before it draws
    anything. **One place owns the prompt**, and with a timeout that place is the
    caller.
    """
    print(_prompt(), end="", flush=True)


def _prompt() -> str:
    """The prompt, in the accent at a terminal and plain everywhere else.

    Only the marker is coloured. What the user types after it is left at the
    terminal's own foreground (#77 AC 30) - the accent marks where the line
    starts; it does not decorate what they say.

    The reset comes before the space rather than after it, so nothing carries
    into the typed line even if a terminal is careless about where a style ends.
    """
    if not _rendering or not sys.stdout.isatty() or _colourless():
        return PROMPT
    red, green, blue = (int(ACCENT[at : at + 2], 16) for at in (1, 3, 5))
    return f"\x1b[1;38;2;{red};{green};{blue}m>\x1b[0m "


def take_back_prompt() -> None:
    """Erase the prompt row, because something is about to be drawn over it.

    Measured on the modelled screen rather than chosen. Without it a scheduled
    turn starts *on* the prompt row and the user reads
    `> axiom: scheduled - ...`, with their own prompt and axiom's line run
    together. Leaving the prompt and starting on the next row instead strands a
    bare `> ` above the turn, which is untidy but not wrong; erasing it is the
    one that reads correctly.

    Only the row the prompt is on. Nothing already in the scrollback is touched,
    which is the same promise `_erase` makes for a line being typed.
    """
    print("\r\x1b[K", end="", flush=True)


def note_scheduled(prompt: str) -> None:
    """A turn that came from a schedule rather than from the user (#74 AC 13).

    In axiom's own voice, not a fourth one. #60 AC 17 is that axiom's lines stay
    distinguishable from the model's, and AC 29 is that everything axiom prints
    which is not the model's reply says what it says today - a scheduled turn is
    new, so it gets `VOICE` like every other thing axiom says about a turn, and
    the model's reply below it is untouched.

    The prompt is echoed because the user did not type it and would otherwise be
    reading an answer to a question they cannot see.
    """
    say(f"scheduled - {prompt}")


def start_turn() -> None:
    """A blank line between what the user typed and what comes back.

    Without it the reply begins on the line directly under the prompt, and a
    conversation of any length reads as one undivided wall - the user's words
    and the model's are the same colour, the same width and hard against each
    other. The gap goes here rather than before the reply text so that
    everything axiom says about this turn - a compaction notice, a tool call,
    an error - falls on the far side of it, inside the block that belongs to
    the turn that caused it.
    """
    print()


def end_turn() -> None:
    """A blank line between the end of a turn and the next prompt.

    The other half of the same problem: without it the next `> ` sits directly
    under the last line of the answer, so the eye cannot find where one
    exchange stopped and the next began. One blank line, once, at the point
    the turn is genuinely over - not after each tool round, which would break
    a single turn into pieces that look like separate ones.

    This is also where the turn's tools are accounted for (#77 AC 24). Here
    rather than at the end of the tool rounds, because a turn can go
    model -> tool -> model -> tool, and the criterion asks for one line when the
    *turn* finishes rather than one per round. **The counters are reset here
    whatever happened**, including on the failure path - every route out of a
    turn passes through this function, and a count that survived one would be
    added to the next turn's.
    """
    global _tool_runs, _tool_failures, _tools_summarised
    _stop_working()
    # Normally already drawn, above the answer, by `show_piece`. This is the
    # turn that never produced another word - out of rounds, or interrupted -
    # where without it the tools that ran would go unmentioned entirely.
    _summarise_tools()
    _tool_runs, _tool_failures, _tools_summarised = 0, 0, False
    print()


def _summarise_tools() -> None:
    """The turn's tools, in one line, once (#77 AC 24, AC 25, AC 26).

    Guarded by a flag rather than by where it is called from: two callers reach
    it - the first fragment of the answer, and the end of a turn that produced no
    answer - and a turn must not be able to get two lines out of them.
    """
    global _tools_summarised
    if _tools_summarised or not _tool_runs:
        # AC 25: nothing at all for a turn that called none, which is what makes
        # the line mean something when it does appear.
        return
    if not _rendering or not sys.stdout.isatty():
        return
    _tools_summarised = True
    word = "tool" if _tool_runs == 1 else "tools"
    failed = f", {_tool_failures} failed" if _tool_failures else ""
    print(_grey(f"  ·  {_tool_runs} {word}{failed}"))


_tools_summarised = False


# Lines of a fenced block kept as context for highlighting the next one. See
# `Rendered._code_line` for the measurement that chose it.
CODE_CONTEXT = 20

# Leading spaces that make a line a code block rather than prose. Markdown's own
# number, and #76 AC 4 is the whole reason it is not the only test applied - a
# list item four spaces in is a list item, and this indent means code only where
# no list is open.
INDENT_IS_CODE = 4


class Rendered:
    """A reply turned into formatted lines, each written exactly once.

    The shape is settled by measurement, in `logs/cycle-1.md`. Rich's `Live` -
    which every published streaming-markdown implementation uses - emits
    `CURSOR_UP` and `ERASE_IN_LINE` once per line of the previous render on
    *every* chunk, and truncates to the screen height with an ellipsis when the
    render is taller than the terminal. On a long reply that means only the last
    screenful is ever visible while it streams, and everything above it is
    rewritten continuously.

    So `Live` is not used. A line is written when it is complete, with an
    ordinary write, and from that moment it belongs to the terminal's scrollback
    and is never addressed again. **No cursor-up sequence is ever emitted**,
    which is a stronger promise than "does not move" and is what the tests
    assert.

    The line still being typed is echoed plainly as it arrives, so no character
    waits for the one after it, and it is re-drawn *in place* with a carriage
    return once it is complete and can be styled. That redraw touches one line,
    never leaves it, and never reaches anything already committed - which is the
    resolution of AC 7 against AC 10, recorded in the cycle log.
    """

    def __init__(self, write=None) -> None:
        self._write = write or (lambda text: print(text, end="", flush=True))
        self._line = ""  # the line being typed, not yet complete
        self._echoed = 0  # how much of it the user has already seen
        self._echo_width = 0  # the width it was drawn at, for taking it back
        self._fence: str | None = None  # the language of an open fence
        self._lexer: str | None = None  # that language, if one exists for it
        self._code: list[str] = []  # the open fence's lines, for context
        self._table: list[str] = []  # rows waiting for the table to end
        self._levels: list[int] = []  # indents of the open list levels (#73)

    def feed(self, text: str) -> None:
        """Take a fragment of the reply and show what can now be shown."""
        self._line += text
        while "\n" in self._line:
            line, _, self._line = self._line.partition("\n")
            self._finished(line)
            self._echoed, self._echo_width = 0, 0
        # Whatever is left is incomplete. Echo the part not yet seen, plainly -
        # holding it back until the newline would make output arrive a line at
        # a time, which is visibly slower than today (AC 10).
        want = self._echo_limit()
        if want > self._echoed:
            self._write(self._line[self._echoed : want])
            self._echoed = want
            # The width *this* text was drawn at. Taking it back later must use
            # the same number - see `_rows_used`.
            self._echo_width = _width()

    def _echo_limit(self) -> int:
        """How much of the unfinished line may be echoed - all but the boundary.

        A terminal that has been sent exactly as many characters as it has
        columns is in an ambiguous state: the VT-series and xterm hold the
        cursor at the last column with the wrap *pending*, while a simpler
        terminal has already moved to the next row. `_erase` cannot tell which,
        and being wrong either leaves a duplicated row behind or climbs one row
        too far and erases a line already committed.

        Rather than pick a side, the boundary is never reached: one character is
        held back whenever the echo would land exactly on a multiple of the
        width. It arrives with the next chunk, or with the line - so it costs a
        few hundred microseconds and removes the whole class.
        """
        full = len(self._line)
        try:
            from rich.cells import cell_len

            width = max(1, _width())
            if full and cell_len(self._line[:full]) % width == 0:
                return full - 1
        except Exception:
            pass
        return full

    def finish(self) -> None:
        """Flush a reply that ended without a final newline."""
        if self._line:
            self._finished(self._line)
        self._settle_table()
        self._line, self._echoed, self._echo_width = "", 0, 0
        self._fence, self._lexer, self._code = None, None, []
        self._levels = []

    def _finished(self, line: str) -> None:
        """One complete line: committed now, or held because it is a table.

        A table is the one construct that cannot be drawn a line at a time -
        the column widths are not known until the last row has arrived, and a
        row rendered alone is just its own text. It is also the only construct
        held back, and that is a rule rather than a habit: AC 8 forbids holding
        a fence's contents, and AC 10 forbids holding anything else.

        Holding costs nothing that was ever shown. A held row is erased from
        the line it was typed on, so the next row is typed over it, and when
        the table ends the whole of it is written at once. Nothing that
        reached the scrollback is touched, so AC 7 still holds exactly.
        """
        if self._fence is None and _looks_like_a_table_row(line):
            self._table.append(line)
            self._write(self._erase(line))  # take back the row typed here
            return
        self._settle_table()
        self._commit(line)

    def _settle_table(self) -> None:
        """Write the held rows as one table, now that its extent is known."""
        if not self._table:
            return
        rows, self._table = self._table, []
        for line in _as_table(rows):
            self._write("\r\x1b[K" + line + "\n")

    def _commit(self, line: str) -> None:
        """Write one finished line, styled, replacing whatever was echoed."""
        self._write(self._erase(line) + self._styled(line) + "\n")

    def _erase(self, typed: str) -> str:
        """Take back the line being typed - all of it, however tall it got.

        `\\r` and erase-to-end-of-line are enough only while the echoed line fits
        the window. A model writes prose as one long line, so it usually does
        not: at 80 columns a paragraph wraps to three rows, `\\r` returns to the
        start of the *third*, and the two rows above it keep the raw text while
        the styled line is written below them. **The paragraph appears twice.**

        Cycles 2 and 3 both marked AC 7 met on the strength of "no cursor-up is
        ever emitted", counted in the byte stream. That promise was a proxy for
        the criterion and it was the wrong proxy: it held perfectly while the
        screen showed every long paragraph twice. Found by modelling a terminal
        rather than counting escapes.

        So the cursor does move up - by exactly the number of rows *this
        unfinished line* occupies, which cannot reach a line already committed.
        That is what AC 7 asks for: nothing shown is repositioned, and nothing
        is printed twice. `\\x1b[J` then clears from there down in one go.
        """
        rows = self._rows_used(typed)
        return "\r" + (f"\x1b[{rows}A" if rows else "") + "\x1b[J"

    def _rows_used(self, typed: str) -> int:
        """Rows below the first that the echoed text has spilled onto.

        `cell_len`, not `len`: a wide character occupies two columns, and
        counting it as one would leave a row behind.

        The width used is the one the text was **echoed** at, not the one in
        force now. A window narrowed between the echo and the newline would
        otherwise make this climb rows the echo never occupied and erase lines
        already committed. Terminals disagree about whether they reflow what is
        already drawn - Windows Terminal does, xterm does not - so there is no
        arithmetic that is right for both. Measuring what was actually emitted
        fails the safe way: leftover text, never a destroyed answer.
        """
        if self._echoed <= 0:
            return 0
        try:
            from rich.cells import cell_len

            width = max(1, self._echo_width or _width())
            return max(0, (cell_len(typed[: self._echoed]) - 1) // width)
        except Exception:
            return 0

    def _styled(self, line: str) -> str:
        """One finished line, as it should look.

        Fence markers open and close a block. Inside one, the line is code:
        highlighted when the fence names a language that exists (AC 2), and
        plain cyan when it names none or names one nobody has a lexer for
        (AC 3) - still set apart from the prose, which is what that criterion
        asks for.

        Nothing below may cost the user the answer (AC 28). `_as_markdown`
        guards itself, but the guard is repeated here because the promise is
        about *any* failure in styling, not about one function's internals -
        and the day someone adds a second renderer above this line, the promise
        should already hold.
        """
        try:
            if line.lstrip().startswith("```"):
                self._open_or_close(line.lstrip()[3:].strip())
                return f"\x1b[2m{line}\x1b[0m"
            if self._fence is not None:
                return self._code_line(line)
            nested = self._nested(line)
            if nested is not None:
                return nested
            indented = self._indented(line)
            return indented if indented is not None else _as_markdown(line)
        except Exception:
            return line

    def _indented(self, line: str) -> str | None:
        """A code block the model indented rather than fenced (#76).

        **After `_nested`, never before it.** The rule Markdown states at the top
        level - four leading spaces is code - is wrong inside a list, where
        nesting is measured from the parent's content column. Placed ahead of the
        list check it turns every nested bullet into a code block: measured, four
        of #73's tests go red along with both of #76's AC 4 pins.

        `self._levels` is the second half of that guard. `_nested` returns `None`
        for a top-level item as well as for a non-item, and a list whose *first*
        line is itself indented would otherwise be read as code by this. A list
        open means this is not.

        **Wrapped here rather than left to the terminal**, for #72's reason: a
        terminal wraps to column zero, and a continuation at column zero is
        indistinguishable from prose. Every row after the first is pushed out to
        the block's own indent, so the block stays a rectangle.

        **The indent is kept, and nothing is painted.** Rich renders one of these
        as a code block with a hardcoded 256-colour background, padded across the
        full width, and cuts the text at the window less two - which is the defect
        #76 was filed for. What sets the block apart here is where it sits, the
        same answer #77 AC 20 reached for a fence with no language: a block nobody
        can lex is delimited, not coloured, because a colour is a claim about the
        content that nothing supports.

        The text is not run through `_as_markdown`. It is code - `**bold**` inside
        it is two asterisks and a word, and rendering it would be the same
        confident lie as colouring it.

        Sliced by character rather than by cell, so a line of wide characters can
        still spill one column and wrap. Every character reaches the screen, which
        is AC 2; the rectangle is what suffers, and no criterion here is about a
        CJK code block. Untested rather than solved, deliberately.
        """
        if self._levels:
            return None
        text = line.lstrip(" ")
        lead = line[: len(line) - len(text)]
        if len(lead) < INDENT_IS_CODE or not text:
            return None
        room = max(1, _width() - len(lead))
        rows = [text[at : at + room] for at in range(0, len(text), room)]
        return "\n".join(lead + row for row in rows)

    def _nested(self, line: str) -> str | None:
        """A list item below the top level, drawn at its own depth.

        `None` for anything that is not one - which is how a flat list keeps
        today's rendering exactly (AC 6). Only a genuinely nested item takes
        this path, so the common case is untouched.

        The renderer has to place the indent itself. `_as_markdown` renders one
        line with no memory of the line before it, so markdown's context is
        gone: an item indented two spaces is indistinguishable from a top-level
        one, and an item indented four is an indented *code block* - which is
        why `'    - Deepest'` came back as three padded rows with blank lines
        around it. Giving Rich the context would mean holding lines back, and
        holding is barred for everything but a table (#60 AC 8 and AC 10).

        So the item's text is rendered alone, as prose - which keeps bold,
        italic, inline code and links working at depth (AC 7) - and the marker
        and the indent are written here.
        """
        match = _LIST_ITEM.match(line)
        if match is None:
            # A blank line may sit inside a list. Anything else ends it, or a
            # list after a paragraph would resume the previous one's depths.
            if line.strip():
                self._levels.clear()
            return None
        spaces, marker, text = match.group(1), match.group(2), match.group(3) or ""
        depth = self._depth(len(spaces))
        if depth == 0:
            return None  # today's path, deliberately untouched
        # An ordered item keeps the number the model wrote; the punctuation goes
        # because Rich drops it at the top level and the two should match.
        glyph = (
            marker.rstrip(".)")
            if marker[:1].isdigit()
            else NESTED_MARKERS[(depth - 1) % len(NESTED_MARKERS)]
        )
        lead = f"{' ' * (1 + NEST_INDENT * depth)}{glyph} "
        if not text.strip():
            return lead.rstrip()
        # Wrapped here rather than left to the terminal. A terminal wraps to
        # column 0, and #72 AC 7 wants the continuation at *this item's* indent -
        # so the text is drawn into the room left beside the marker, and every
        # row after the first is pushed out to where the first row's text began.
        room = max(1, _width() - len(lead))
        rows = _as_markdown(text, width=room, wrapped=True).split("\n")
        drawn = [lead + rows[0]] + [" " * len(lead) + row for row in rows[1:]]
        return _unpadded("\n".join(drawn))

    def _depth(self, indent: int) -> int:
        """Which level an indent is, against the levels seen so far.

        A stack rather than arithmetic. Markdown nests by indent relative to the
        parent's *content* column, which moves with the parent's marker - three
        for `1. `, two for `- ` - so dividing an indent by a fixed width gets
        mixed lists wrong. Deeper than the top pushes a level, shallower pops
        back to the level that matches, equal stays where it is. That is AC 2
        and AC 5 between them, and it needs no lookahead.
        """
        while self._levels and indent < self._levels[-1]:
            self._levels.pop()
        if not self._levels or indent > self._levels[-1]:
            self._levels.append(indent)
        return len(self._levels) - 1

    def _open_or_close(self, language: str) -> None:
        """A fence marker arrived: start a block, or end the one open."""
        if self._fence is not None:
            self._fence, self._lexer, self._code = None, None, []
            return
        self._fence = language or ""
        self._lexer = _lexer_for(self._fence)
        self._code = []

    def _code_line(self, line: str) -> str:
        """One line of a fenced block, highlighted in the block's own context.

        Highlighting a line *alone* guesses at context it does not have - the
        middle of a triple-quoted string is not code, and colouring it as code
        is a confident lie. So the whole block so far is lexed and only the new
        line's rendering is taken. Cheap: a block is tens of lines, and this
        happens once per line rather than once per chunk.

        No line is ever redrawn by this. A line already committed keeps whatever
        it was given, which is right - re-lexing changes the *next* line's
        context, never an earlier line's text.

        The context is **bounded**, and the bound was measured rather than
        picked. Lexing the whole block on every line is quadratic: 7.2ms a line
        at 10 lines, 29ms at 200, **71ms at 500** - 35 seconds of CPU for a
        500-line block, a visible stall and so an AC 10 failure.

        Held to a window the cost is flat and linear in the window: 2.2ms at 5
        lines, 6.1 at 20, 16.0 at 60, 28.3 at 120. Twenty is the choice - well
        inside the gap between two streamed lines, and more context than any
        multi-line string in a chat reply plausibly needs. What it costs is a
        string opened more than twenty lines earlier being coloured as code;
        what it buys is a long block that still streams.
        """
        self._code.append(line)
        del self._code[:-CODE_CONTEXT]
        if self._lexer:
            drawn = _highlighted("\n".join(self._code), self._lexer)
            if len(drawn) >= len(self._code):
                return drawn[len(self._code) - 1]
        # #77 AC 20: no styling at all. If the fence names no language we cannot
        # know how to colour what is inside it, and a colour chosen anyway is a
        # claim about the content that nothing supports.
        #
        # This is a **reinterpretation of #60 AC 3**, "a block reads as a block,
        # named language or not", and it is written down here rather than left to
        # be inferred from an edited test. What sets the block apart is now its
        # fence markers, which `_styled` still draws dim above and below it - the
        # block is delimited rather than painted. Measured before the change:
        # `styling('x = 1') == ''` and `styling('```nosuchlanguage') == '\x1b[2m'`.
        return line


def _lexer_for(language: str) -> str | None:
    """The named language, if anything can actually highlight it.

    Rich falls back to plain text for a name it does not know, silently - so
    asking it is no way to tell a recognised language from an unrecognised one,
    and AC 2 and AC 3 want different things for the two.
    """
    if not language:
        return None
    try:
        from pygments.lexers import get_lexer_by_name

        get_lexer_by_name(language)
        return language
    except Exception:
        return None


def _highlighted(code: str, language: str) -> list[str]:
    """A block of code, drawn one output line per source line.

    A very wide console and no word wrapping, on purpose: the caller places
    lines itself and needs the two to correspond. The terminal does the
    wrapping afterwards, as it does for every other line here.
    """
    try:
        from io import StringIO

        from rich.console import Console
        from rich.syntax import Syntax

        buffer = StringIO()
        Console(
            file=buffer,
            force_terminal=True,
            legacy_windows=False,
            width=10_000,
            no_color=_colourless(),
        ).print(
            Syntax(
                code,
                language,
                theme="ansi_dark",  # the terminal's own colours, not a palette
                background_color="default",  # never paint behind the text
                word_wrap=False,
            ),
            end="",
        )
        return [_unpadded(line) for line in buffer.getvalue().split("\n")]
    except Exception:
        return []


def _colourless() -> bool:
    """Whether the user has asked for no colour.

    Presence, not truth: `NO_COLOR=` with nothing after it counts.

    **This used to claim Rich agreed, and Rich does not.** Measured under #77:
    with `NO_COLOR=` set to the empty string, Rich emits the accent regardless -
    it follows the published convention's "not an empty string" wording. Nothing
    ever caught the disagreement because the only test of this rule went through
    the one colour this module wrote by hand, which obeyed *this* function and
    never asked Rich anything.

    So the two rules were in force at once: with `NO_COLOR=`, a fence lost its
    colour and every heading kept its own. That is the exact inconsistency the
    old docstring said it was avoiding, and it shipped for the whole of #60.

    Presence is kept, because it is the recorded decision and it is the stricter
    of the two - a user who writes `NO_COLOR=` meant something by it. It is now
    imposed on Rich rather than assumed of it: every Console that draws is built
    with `no_color=` from here, so one rule reaches the whole screen.
    """
    return "NO_COLOR" in os.environ


# A row of a table, kept deliberately tight: a line whose first non-space
# character is a pipe. Markdown allows a table without leading pipes, but
# treating any line *containing* one as a table row would swallow ordinary
# prose - a shell pipeline, a regex alternation - into a table that never
# closes. Missing a table reads badly; eating a paragraph loses the answer.
_TABLE_ROW = re.compile(r"^\s*\|")

# What Rich draws inside a container: a block quote, a list item. Inside one,
# `soft_wrap` stops meaning "let the terminal wrap it" and becomes no-wrap in a
# fixed-width box - and the box **crops**. Measured at 60 columns: a 182-
# character quote came back 58 characters long and the rest was simply gone; a
# line one character wider than the window lost exactly that one character.
#
# Letting Rich wrap these costs nothing and buys most of the issue. It carries
# the quote's marker onto every continuation row (AC 5), aligns a list item's
# continuation under its text rather than its marker (AC 6), and folds an
# unbroken token longer than the window without losing a character of it (AC 14).
#
# Bare text is deliberately absent. A paragraph is emitted as one long line and
# the *terminal* wraps it, which is why a resize reflows it. Pre-wrapping it
# through Rich would look identical at first and then stop reflowing, which is
# AC 10 and AC 18 both.
_CONTAINED = re.compile(r"^\s*(>|[-*+]\s|\d{1,9}[.)]\s)")

# A list item: its indent, its marker, and the text after it. The text is
# optional so a marker on its own is still an item (#73 AC 8), and a space is
# required before any text so `-a-b` stays the prose it is rather than becoming
# a bullet.
_LIST_ITEM = re.compile(r"^(\s*)([-*+]|\d{1,9}[.)])(?:\s+(.*))?$")

# One marker per depth, so a level is apparent from the glyph and not only from
# the indent (#73 AC 4). Top level is absent from this: it keeps whatever Rich
# already draws, because AC 6 says a flat list must not change.
NESTED_MARKERS = ("◦", "▪", "•")  # ring, small square, bullet
NEST_INDENT = 2  # columns a level is indented by

# The one accent, and the grey axiom speaks in (#77).
#
# ACCENT is Mountain Leverage's own `--uicore-secondary-color`, read off their
# theme stylesheet. VOICE_GREY is their `--uicore-body-color`, `rgba(16,24,40,.6)`
# resolved over white - derived rather than published, and chosen over a lighter
# grey because axiom does not know whether it is on a light or a dark background
# and this one survives both.
ACCENT = "#daa900"
VOICE_GREY = "#70747e"

# What Rich paints a reply with. Without this it uses its own defaults - magenta
# for quotes and h2-h4, cyan for inline code, list numbers and table borders,
# bright_blue for links. Three hues that axiom never chose and that have nothing
# to do with each other (#77 AC 17, AC 18).
#
# Two entries are deliberately left at Rich's value rather than accented:
#
#   markdown.code_block   a fenced block with a *known* language is drawn by
#                         `_highlighted` against ansi_dark, because a language
#                         needs more than one hue to be readable (AC 19). This
#                         style only ever reaches a block nobody has a lexer for,
#                         and AC 20 says that one carries no styling at all.
#   markdown.h1.border    Rich draws no border for h1 here; naming it would be
#                         asserting a decision this issue does not make.
_MARKDOWN_STYLES = {
    "markdown.block_quote": f"dim {ACCENT}",
    "markdown.code": f"bold {ACCENT} on black",
    "markdown.h1": f"bold {ACCENT}",
    "markdown.h2": f"bold {ACCENT}",
    "markdown.h3": ACCENT,
    "markdown.h4": f"italic {ACCENT}",
    "markdown.h5": "italic dim",
    "markdown.h6": "dim",
    "markdown.hr": "dim",
    "markdown.item.bullet": f"bold {ACCENT}",
    "markdown.item.number": ACCENT,
    "markdown.kbd": f"bold {ACCENT}",
    "markdown.link": f"underline {ACCENT}",
    "markdown.link_url": "dim underline",
    "markdown.list": ACCENT,
    "markdown.table.border": ACCENT,
    "markdown.table.header": f"bold {ACCENT}",
}


def _theme():
    """The palette, built once and handed to every Console that draws a reply.

    A function rather than a module-level object because `rich.theme` is imported
    lazily everywhere else in this file - the import cost belongs to the first
    render, not to starting up.

    `NO_COLOR` needs nothing here. Rich honours it natively and strips the accent
    while leaving bold, dim and underline alone, which is what the convention asks
    for and what axiom already decided to defer to (AC 31).
    """
    global _THEME
    if _THEME is None:
        from rich.theme import Theme

        _THEME = Theme(_MARKDOWN_STYLES)
    return _THEME


_THEME = None

# What Rich draws under a table's header row, and the sign that it understood
# the rows as a table at all rather than as a paragraph of pipes.
HEADER_RULE = "─"


def _is_a_rule(line: str) -> bool:
    """Whether a drawn line is a header rule and not text that contains one.

    A whole line of it, not an appearance of it. Asking whether the character
    is *present* takes a row like `| a─b | c |` - a model drawing a diagram in
    a table cell - as proof that a table was drawn, and hands back the
    paragraph Rich actually produced, with every row run together.
    """
    visible = _ESCAPE.sub("", line)
    return bool(visible.strip()) and not visible.strip(" " + HEADER_RULE)


def _looks_like_a_table_row(line: str) -> bool:
    return bool(_TABLE_ROW.match(line))


def _as_table(rows: list[str]) -> list[str]:
    """The held rows drawn as one table, or handed back untouched.

    Whether Rich *drew a table* is asked explicitly, by looking for the rule it
    puts under a header. It is not enough that it returned something: handed
    rows it cannot parse - a delimiter row narrower than the header, which AC 23
    names - it draws them as one paragraph, and four rows come back run together
    into a single wrapped line of pipes. The rows are all there and unreadable.

    So anything that is not a table goes back exactly as the model wrote it, one
    line per row. This is AC 5 and AC 23 at the one place in the renderer that
    holds anything.
    """
    try:
        from io import StringIO

        from rich.console import Console
        from rich.markdown import Markdown

        buffer = StringIO()
        Console(
            file=buffer,
            force_terminal=True,
            legacy_windows=False,
            width=_width(),
            soft_wrap=False,  # a table draws its own edges; do not let them wrap
            theme=_theme(),  # #77 AC 17 - the rules carry the accent
            no_color=_colourless(),
        ).print(Markdown("\n".join(rows)), end="")
        drawn = [_unpadded(line) for line in buffer.getvalue().split("\n")]
        # Rich draws a top and bottom border row for a table, and the box style
        # it uses for markdown puts nothing in them - so they arrive as lines
        # that are empty apart from their escape sequences, and a blank line
        # either side of every table. `strip()` does not see them as empty
        # because an escape sequence is not whitespace.
        while drawn and not _visible(drawn[0]):
            drawn.pop(0)
        while drawn and not _visible(drawn[-1]):
            drawn.pop()
        if not any(_is_a_rule(line) for line in drawn):
            return rows  # not a table; hand back what the model wrote
        return drawn or rows
    except Exception:
        # AC 28, and AC 5. A table that cannot be drawn is still a table the
        # user asked for; hand back exactly what the model wrote.
        return rows


def _as_markdown(
    line: str, width: int | None = None, wrapped: bool | None = None
) -> str:
    """One line through Rich, without letting it own the cursor or the width.

    `width` and `wrapped` are for a caller drawing inside its own margin - a
    nested list item, which has to wrap to *its* indent rather than to the
    terminal's left edge (#72 AC 7). Everything else leaves both alone and gets
    the window's width and the per-construct choice below.

    Rich pads a rendering to the console width and puts a blank line before a
    list item; neither belongs here, where the caller is placing lines itself.
    A line Rich cannot make sense of comes back as it went in - never dropped,
    which is AC 5 and the failure mode markdown renderers are prone to.

    `legacy_windows=False` is not cosmetic. Rich detects the old Windows console
    and, believing it cannot emit a hyperlink, renders `[the docs](https://...)`
    as the four words `see the docs for more` - **the address is gone**, with no
    way for the user to read or copy it. Measured, not assumed: with the flag it
    emits the OSC-8 sequence and the address survives. Anything axiom runs on is
    a terminal from this decade.
    """
    if not line.strip():
        return line
    try:
        from io import StringIO

        from rich.console import Console
        from rich.markdown import Markdown

        buffer = StringIO()
        Console(
            file=buffer,
            force_terminal=True,
            legacy_windows=False,  # or a link's address is dropped; see above
            width=width or _width(),
            # Off for anything Rich draws in a container, on for everything
            # else. See `_CONTAINED` - this one flag is the whole of #72.
            soft_wrap=(not _CONTAINED.match(line)) if wrapped is None else not wrapped,
            theme=_theme(),  # #77 AC 17, AC 18 - one accent, not Rich's three hues
            no_color=_colourless(),  # presence, imposed rather than assumed
        ).print(Markdown(line), end="")
        shown = buffer.getvalue().strip("\n")
        return _unpadded(shown) if shown.strip() else line
    except Exception:
        # AC 28. A formatting failure costs the formatting, never the answer.
        return line


# Trailing spaces Rich adds to pad a block element - a quote, a heading - out to
# the console width. A line padded to exactly the width, plus the newline this
# module writes, wraps to a blank line on most terminals (AC 12). `rstrip` alone
# does not reach them: the padding sits *before* the closing reset sequence.
#
# `MULTILINE`, because a rendering can now be more than one line. Without it `$`
# is end-of-*string* and only the last line is reached - which was harmless while
# every rendering was one line, and becomes a double-spaced quote the moment one
# wraps (#72). Measured before the change: `_unpadded('a   \nb   ')` returned
# `'a   \nb'`.
_PADDING = re.compile(r"[ \t]+(?=(?:\x1b\[[0-9;]*m)*$)", re.MULTILINE)
_ESCAPE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")


def _unpadded(shown: str) -> str:
    return _PADDING.sub("", shown)


def _visible(line: str) -> bool:
    """Whether a line puts anything on the screen, escapes aside."""
    return bool(_ESCAPE.sub("", line).strip())


def _width() -> int:
    """The terminal's width, or a sane column count when there is no terminal."""
    try:
        import shutil

        return max(20, shutil.get_terminal_size().columns)
    except Exception:
        return 80


_reply: "Rendered | None" = None
_rendering = True


def use_rendering(enabled: bool) -> None:
    """Whether replies are formatted at all this run (AC 25).

    Set once from the resolved settings. Off takes the same path a redirected
    run takes, rather than a quieter rendering - so "off" is the behaviour the
    golden transcript already records, and there is one plain path rather than
    two that have to be kept identical.
    """
    global _rendering
    _rendering = enabled


def show_piece(text: str) -> None:
    """A fragment of the model's reply, as it arrives.

    Plain and unbuffered when output is not a terminal - byte for byte what a
    redirected or piped run produced before any of this existed, which is what
    keeps the golden transcript and `axiom | grep` working.
    """
    global _reply
    if not _rendering or not sys.stdout.isatty():
        print(text, end="", flush=True)
        return
    # #77 AC 24: the turn's tools are accounted for **before** the answer they
    # produced, not after it.
    #
    # It used to be drawn in `end_turn`, which put it below the answer and
    # between two blank lines - so it read as belonging to the next prompt, and
    # you learned what the answer rested on only after you had read it. Driven by
    # hand on 2026-09-01: a turn that ran one tool and answered "I do not have a
    # tool available" showed `·  1 tool` underneath, and nothing on screen
    # resolved the contradiction until you scrolled back to look at it again.
    #
    # Here rather than at the end of the tool rounds because a turn can go
    # model -> tool -> model -> tool: this fires on the first fragment of reply
    # that follows any tool call, which is one line per turn wherever the rounds
    # fall. `end_turn` still draws it if a turn ended without another word - out
    # of rounds, or interrupted - so it is never simply lost.
    _summarise_tools()
    if _reply is None:
        _reply = Rendered()
    _reply.feed(text)


def _settle_reply() -> None:
    """Finish and let go of any reply still being rendered.

    Does nothing at all when there is none - which is every plain-path run, so
    the bytes a redirected run produces are untouched.
    """
    global _reply
    if _reply is not None:
        _reply.finish()
        _reply = None


def end_reply() -> None:
    _settle_reply()
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
    global _tool_runs
    if _rendering and sys.stdout.isatty():
        # #77 AC 22: nothing per call. What the user gets instead is AC 23 - a
        # line saying something is running, which is taken back the moment the
        # result arrives. A tool phase is seconds long and a silent pause reads
        # as a hang, which `note_starting` already says out loud.
        _tool_runs += 1
        _start_working(name)
        return
    if isinstance(arguments, dict):
        detail = ", ".join(f"{key}={value}" for key, value in arguments.items())
    else:
        # A call announced as text can carry anything at all. Show it as it
        # came - running it is what reports that it cannot be used.
        detail = str(arguments)
    say(f"{name}({detail})")
    for path in outside or []:
        say(f"outside the working directory: {path}")


# What this turn's tools did, for the one line that replaces all of them. Reset
# by `end_turn`, which every route out of a turn goes through - including the
# one that failed, or a turn that ended badly would spill its count into the next.
_tool_runs = 0
_tool_failures = 0
_working = False


def _start_working(name: str) -> None:
    """One transient line while a tool runs (#77 AC 23).

    `\\r` then erase-to-end-of-line, which is the pair `Rendered` already uses to
    replace an echoed line with a styled one. Nothing is committed: the row is
    overwritten by the next call and taken back entirely by `_stop_working`, so
    a turn calling four tools leaves no trail of four lines behind it.
    """
    global _working
    _working = True
    print(f"\r\x1b[K  {_grey('· ' + name + ' ...')}", end="", flush=True)


def _stop_working() -> None:
    """Take the transient line back, leaving the row as it was."""
    global _working
    if _working:
        print("\r\x1b[K", end="", flush=True)
        _working = False


def _grey(text: str) -> str:
    """axiom's own voice, quieter than the answer (#77 AC 27).

    A colour, so `NO_COLOR` takes it - which leaves the words, which is the
    point: quieter is a preference, legible is not.
    """
    if _colourless():
        return text
    red, green, blue = (int(VOICE_GREY[at : at + 2], 16) for at in (1, 3, 5))
    return f"\x1b[38;2;{red};{green};{blue}m{text}\x1b[0m"


def note_round_limit(rounds: int) -> None:
    """The turn ended because it ran out of rounds, not because it answered.

    Without this the user gets whatever `reply` happened to hold, which after
    a turn that called tools every round is nothing at all (#41 AC 10).
    """
    say(
        f"stopped after {rounds} rounds of tool calls without an answer. "
        f"Nothing further was tried."
    )


def show_tool_result(result: str) -> None:
    """A tool's output, marked so it cannot be read as the model's answer.

    At a terminal this shows **nothing** (#77 AC 26). The per-call detail leaves
    the screen entirely and one summary line replaces the lot; the detail is
    bound for a log, which is its own piece of work. What happens here instead is
    that the transient line is taken back and the outcome is counted.

    Not at a terminal it is unchanged, which is what keeps the golden transcript
    still and AC 33 true.
    """
    global _tool_failures
    if _rendering and sys.stdout.isatty():
        _stop_working()
        # The convention every tool already follows for a failure, and the one a
        # user would recognise: a result that opens by saying it is an error.
        if result.startswith("error:"):
            _tool_failures += 1
        return
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
        say("read: " + ", ".join(read))
    only_seen = [address for address in seen if address not in read]
    if only_seen:
        say("found, not read: " + ", ".join(only_seen))


def note_compaction(kept_pairs: int) -> None:
    level = "everything" if kept_pairs == 0 else f"keeping the last {kept_pairs}"
    say(f"compacting older history ({level})")


def note_facts_forgotten(dropped: list[str]) -> None:
    """Said when the summary reached its bound and the oldest facts were let go.

    Named one by one rather than counted. #32 asks that a long session never
    *silently* loses information - not that it never loses any, which is not
    arithmetically available - and a count tells the user something went
    without telling them whether it mattered. Seeing it is what lets them say
    it again if it did.
    """
    say(f"the summary is full - forgetting {len(dropped)}:")
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

    The pending reply is settled first. This is the only route out of a turn
    that does not pass `end_reply`, so without it the renderer keeps the dead
    turn's half-line and feeds the *next* answer into it - a fresh question
    after a dropped connection came back as `partial a fresh answer`, with the
    failed reply glued to the front of a new one. Settling here rather than at
    the call site because this is the function that cannot be forgotten, and
    settling after the message would erase it: the erase runs to the end of the
    screen, and by then the message is on it.
    """
    _settle_reply()
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


def show_skills(listed: list[tuple[str, str]], where: str) -> None:
    """The skills that loaded, one to a line, name and description (AC 5).

    `where` is said only when there are none. A user with skills already knows
    where they live; a user with none is the only one who needs telling, and
    AC 6 asks for both halves of that - that there are none, and where one would
    go. Saying the path every time would be noise for everyone it cannot help.
    """
    if not listed:
        say(f"no skills loaded. A skill is a folder in {where} with a SKILL.md")
        return
    word = "skill" if len(listed) == 1 else "skills"
    say(f"{len(listed)} {word}:")
    for name, description in listed:
        say(f"  {name} - {description}")


def note_skill(name: str) -> None:
    """Which skill is being followed, before the reply begins (AC 11).

    Shaped like `note_tool`, deliberately. AC 14 says a skill the *model*
    invokes is shown the way a tool call is shown - which it already is, because
    that path goes through `note_tool` like any other tool. A user typing
    `/skill` reaches the same behaviour by a different route, and the two should
    not end up looking like different features.
    """
    say(f"skill: {name}")


def note_no_skill(name: str, available: tuple[str, ...]) -> None:
    """No skill by that name, and what there is instead (AC 9, AC 10).

    Two cases, one function: no name typed at all, and a name that matches
    nothing. Both end the same way - the user needs the list - and splitting
    them would mean two messages that have to be kept saying the same thing.

    The alternatives are named rather than counted. A user who mistyped one
    character can fix it from this line; a user told only "no such skill" has to
    go and run `/skills` to find out what they meant.
    """
    listed = ", ".join(available) or "none"
    if not name:
        say(f"name a skill: /skill <name>. Available: {listed}")
        return
    say(f"there is no skill named {name}. Available: {listed}")


def note_skills_off() -> None:
    """Skills were switched off for this run (AC 38).

    Distinct from "no skills loaded", deliberately. That message tells a user
    where to put one; this one would be a lie if it did, because a skill written
    into that folder would not be read. The difference is between having none
    and having asked for none.
    """
    say("skills are off for this run (--no-skills or $AXIOM_SKILLS)")


def note_skills(
    loaded: int,
    problems: list[str],
    cost: int | None = None,
    enabled: bool = True,
) -> None:
    """How many skills loaded, what they cost, and anything that did not (AC 2, 3, 4).

    Said only when there is something to say. A run with no skills directory is
    a run that looks exactly as it did before skills existed, which is AC 1 - so
    zero loaded and nothing wrong produces no line at all.

    Problems are named one by one rather than counted, the same reasoning as
    `note_servers`: each is fixed by a different action - adding a description,
    creating the SKILL.md, renaming one of two that clash - and a count says
    none of that.

    The cost is the skills' own share, not the total. `note_tool_cost` already
    reports what every request carries; what a user cannot get from that is
    whether the skills are the expensive part, which is the question AC 3 exists
    to answer.
    """
    # Off is said; empty is not. AC 39 asks the user be told whether skills are
    # on, and a run that was told to switch them off should confirm it did.
    # A run with skills on and no directory says nothing at all, which is AC 1 -
    # the two states are different and only one of them was asked for.
    if not enabled:
        say("skills off")
        return
    if not loaded and not problems:
        return
    if loaded:
        word = "skill" if loaded == 1 else "skills"
        share = f", about {cost} tokens per request" if cost else ""
        say(f"{loaded} {word} loaded{share}")
    for problem in problems:
        say(f"skill not loaded - {problem}")


def note_skill_too_large(name: str, over: int) -> None:
    """A skill that cannot fit the window is not sent, and is named (AC 29).

    Named, because "this message is too large" sends a user looking at what they
    typed - and they typed `/skill release-checklist`, which is nineteen
    characters. The thing that is too large is the file behind it, and only this
    line says so.
    """
    say(
        f"{name} is about {over} tokens too large for this model's "
        f"window - not sent. Shorten the skill, or switch to a model with more "
        f"room with /model."
    )


# --- #77: the session's facts ----------------------------------------------


def show_facts(
    *,
    model: str,
    host: str,
    context: "int | None",
    overridden: bool,
    tools: "int | None",
    web: bool,
    cost: "int | None",
    connected: dict,
    problems: list,
    bounds: "tuple[float, float] | None",
    skills_loaded: int,
    skill_problems: list,
    skills_cost: "int | None",
    skills_enabled: bool,
    reason: str = "",
) -> None:
    """What this session is: the model, the host, the room, the cost (#77 AC 11).

    **Two renderers, one set of facts, and the split is not cosmetic.** AC 33
    requires redirected and piped output to be unchanged byte for byte, and the
    golden transcript is captured from a `StringIO` - not a terminal. So the
    panel is drawn only at a terminal and a redirected run takes exactly the path
    it took before #77 existed.

    That is the same shape `use_rendering` already chose for replies: one plain
    path, which is the one the transcript records, and a rendered path on top of
    it. It also means **the 78 baseline lines this issue was expected to rewrite
    do not change at all** - the narrowing #75 asks for, found by asking whether
    the code could be shaped so the baseline is restored rather than updated.

    The plain path calls the four functions in the order they were called in
    before, and they are unchanged. Nothing is duplicated: the panel reads the
    same arguments rather than a second set of sentences.
    """
    # `_rendering` as well as the terminal. `--no-render` takes the same path a
    # redirected run takes rather than a quieter rendering (AC 32) - which is the
    # rule `use_rendering` already states for replies, and a panel drawn under it
    # would have made "off" mean two different things in one session.
    if not _rendering or not sys.stdout.isatty():
        announce(model, host, context, overridden=overridden, tools=tools, web=web)
        note_servers(connected, problems, bounds=bounds)
        note_tool_cost(cost, context)
        note_skills(skills_loaded, skill_problems, skills_cost, enabled=skills_enabled)
        return

    _clear_screen()
    _facts_panel(
        model=model,
        host=host,
        context=context,
        overridden=overridden,
        tools=tools,
        web=web,
        cost=cost,
        connected=connected,
        bounds=bounds,
        skills_loaded=skills_loaded,
        skills_cost=skills_cost,
        skills_enabled=skills_enabled,
        reason=reason,
    )
    # Outside the box, on the streams they already used (#77 AC 16). A border
    # around a failure makes it look like part of the report rather than
    # something to do, and each of these is fixed by a different action.
    for problem in problems:
        say(f"{problem}", sys.stderr)
    for problem in skill_problems:
        say(f"skill not loaded - {problem}")


def _clear_screen() -> None:
    """The screen, not the scrollback (#77 AC 7, AC 9).

    `\x1b[2J\x1b[H` - erase the display and home the cursor. Deliberately not
    `\x1b[3J`, which also empties the scrollback buffer: a user who scrolls up
    after choosing a model should still find what was there. The two look
    identical the moment they are run and differ only in what is recoverable,
    which is exactly the kind of difference that needs asserting on the bytes.
    """
    print("\x1b[2J\x1b[H", end="")


def _facts_panel(
    *,
    model: str,
    host: str,
    context: "int | None",
    overridden: bool,
    tools: "int | None",
    web: bool,
    cost: "int | None",
    connected: dict,
    bounds: "tuple[float, float] | None",
    skills_loaded: int,
    skills_cost: "int | None",
    skills_enabled: bool,
    reason: str,
) -> None:
    """The facts as a label/value grid, in the same border as the model list.

    **A row exists only where the plain path prints a line** (#77 AC 12). That is
    the whole rule, and it is what keeps a bare run bare: no skills directory
    means no skills row, exactly as `note_skills` says nothing at all in that
    case, and an unknown cost is left out rather than shown as zero - a zero is a
    number and reads like one.
    """
    try:
        from rich.box import ROUNDED
        from rich.console import Console
        from rich.panel import Panel
        from rich.table import Table
        from rich.text import Text

        grid = Table.grid(padding=(0, 2))
        grid.add_column(justify="right", style=f"dim default {VOICE_GREY}")
        grid.add_column()

        def row(label: str, value: Text) -> None:
            grid.add_row(Text(label, style=VOICE_GREY), value)

        name = Text(model, style=f"bold {ACCENT}")
        because = settled_because(reason)
        if because:
            # On the model's row rather than as a statement of its own: it
            # explains that value, and is not a fact beside it (#77 AC 15).
            name.append(f"   {because}", style=VOICE_GREY)
        row("model", name)
        row("host", Text(host, style=VOICE_GREY))

        room = Text(_room(context, overridden))
        row("context", room)

        row("tools", Text(_can_do(tools, web)))

        if cost is not None:
            share = f", {100 * cost / context:.0f}% of the window" if context else ""
            spend = Text(f"~{cost} tokens")
            spend.append(f" per request{share}", style=VOICE_GREY)
            row("cost", spend)

        first = True
        for server, count in (connected or {}).items():
            word = "tool" if count == 1 else "tools"
            line = Text(server)
            line.append(f"  {count} {word}", style=VOICE_GREY)
            row("servers" if first else "", line)
            first = False
        if connected and bounds:
            start, call = bounds
            row(
                "",
                Text(f"start limit {start:g}s, call limit {call:g}s", style=VOICE_GREY),
            )

        if not skills_enabled:
            row("skills", Text("off", style=VOICE_GREY))
        elif skills_loaded:
            word = "skill" if skills_loaded == 1 else "skills"
            loaded = Text(f"{skills_loaded} {word}")
            if skills_cost:
                loaded.append(f"  ~{skills_cost} tokens per request", style=VOICE_GREY)
            row("skills", loaded)

        Console(
            force_terminal=True,
            legacy_windows=False,
            no_color=_colourless(),
            width=_width(),
        ).print(
            Panel(
                grid,
                title=Text("axiom", style=f"bold {ACCENT}"),
                title_align="left",
                border_style=ACCENT,
                box=ROUNDED,
                padding=(1, 2),
                expand=False,
            )
        )
    except Exception:
        # The same trade every other renderer here makes: formatting is what a
        # failure costs, never the facts.
        announce(model, host, context, overridden=overridden, tools=tools, web=web)
        note_tool_cost(cost, context)

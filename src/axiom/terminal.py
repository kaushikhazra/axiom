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

    Numbers are right-aligned so a ten-model host does not stagger the names.
    """
    print(f"{VOICE} models on {host}")
    width = len(str(len(models)))
    label = "  (current)" if current else "  (default)"
    # Annotated only where it explains something (#52 AC 8): a host whose
    # models can *all* call tools, or none of which can, has an order that is
    # plain name order, and a note on every row would explain nothing while
    # making every row longer. Mixed hosts are the case the ordering exists
    # for, and the only case where a reader needs to be told why.
    mixed = capable is not None and 0 < len(capable) < len(models)
    for number, model in enumerate(models, start=1):
        tools = "  tools" if mixed and model in capable else ""
        print(f"  {number:>{width}}. {model}{tools}{label if model == marked else ''}")
    if capable is not None and not capable:
        # AC 9. Said once rather than per row - it is a fact about the host,
        # not about any one model, and without it the order looks arbitrary.
        print(f"{VOICE} none of these can call tools")


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
        print(f"{VOICE} there is no model {given} - {wanted}", file=sys.stderr)
    else:
        print(f"{VOICE} {given!r} is not a number - {wanted}", file=sys.stderr)


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
        print(f"{VOICE} {problem} - it will be asked again next time", file=sys.stderr)
    elif path:
        print(f"{VOICE} remembering this choice in {path}")


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
    print(
        f"{VOICE} now {model} "
        f"(context: {_room(context, overridden)}, {_can_do(tools, web)})"
    )


def note_unchanged(model: str) -> None:
    """Nothing happened, said so the silence is not mistaken for a switch."""
    print(f"{VOICE} still {model}")


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
    print(
        f"{VOICE} still on {model}, which {host} no longer lists",
        file=sys.stderr,
    )


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
    print(
        f"{VOICE} {model} at {host} "
        f"(context: {_room(context, overridden)}, {_can_do(tools, web)})"
    )


def note_starting(servers: int) -> None:
    """Said before the wait, because starting a server can take seconds.

    A silent pause before the first prompt reads as a hang, and the user has no
    way to tell one from the other.
    """
    if servers:
        word = "server" if servers == 1 else "servers"
        print(f"{VOICE} starting {servers} MCP {word}...")


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
    print(f"{VOICE} tools cost about {cost} tokens per request{share}")


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
        print(f"{VOICE} {name}: {count} {tools_word}")

    if connected and bounds is not None:
        start, call = bounds
        print(f"{VOICE} server start limit {start:g}s, tool call limit {call:g}s")

    for problem in problems:
        print(f"{VOICE} {problem}", file=sys.stderr)


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
        self._lines: "queue.Queue[str | None]" = queue.Queue()
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
            return input(PROMPT).strip()
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
    print(PROMPT, end="", flush=True)


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
    print(f"{VOICE} scheduled - {prompt}")


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
    """
    print()


# Lines of a fenced block kept as context for highlighting the next one. See
# `Rendered._code_line` for the measurement that chose it.
CODE_CONTEXT = 20


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
            return _as_markdown(line)
        except Exception:
            return line

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
        # Cyan is a colour, so `NO_COLOR` takes it. The dim on a fence marker is
        # an attribute rather than a colour and stays - which is the line Rich
        # draws, and the line the convention draws.
        return line if _colourless() else f"\x1b[36m{line}\x1b[0m"


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
            file=buffer, force_terminal=True, legacy_windows=False, width=10_000
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

    Presence, not truth: `NO_COLOR=` with nothing after it counts. The published
    convention says "not an empty string", but Rich tests for presence, and Rich
    draws most of what reaches the screen here. Agreeing with the renderer beats
    agreeing with the specification and then disagreeing with itself - a session
    where headings lose their colour and fenced code keeps it is the worse
    outcome of the two.
    """
    return "NO_COLOR" in os.environ


# A row of a table, kept deliberately tight: a line whose first non-space
# character is a pipe. Markdown allows a table without leading pipes, but
# treating any line *containing* one as a table row would swallow ordinary
# prose - a shell pipeline, a regex alternation - into a table that never
# closes. Missing a table reads badly; eating a paragraph loses the answer.
_TABLE_ROW = re.compile(r"^\s*\|")

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


def _as_markdown(line: str) -> str:
    """One line through Rich, without letting it own the cursor or the width.

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
            width=_width(),
            soft_wrap=True,
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
_PADDING = re.compile(r"[ \t]+(?=(?:\x1b\[[0-9;]*m)*$)")
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

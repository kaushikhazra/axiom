"""Everything the user sees and types.

The only module under src/ that calls print() or input(). The chat loop asks
this module to say things rather than saying them itself, which is what keeps
one module from both talking to a backend and writing to a terminal.
"""

import sys

from .backend import ConnectionLost

PROMPT = "> "
VOICE = "axiom:"  # how axiom identifies its own lines, as opposed to the model's


def announce(model: str, host: str, context: int | None, overridden: bool) -> None:
    """The startup line: what we are talking to, and with how much room."""
    if context is None:
        note = "Ollama default"
    else:
        note = f"{context} tokens{', debug override' if overridden else ''}"
    print(f"{VOICE} {model} at {host} (context: {note})")


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


def note_compaction(kept_pairs: int) -> None:
    level = "everything" if kept_pairs == 0 else f"keeping the last {kept_pairs}"
    print(f"{VOICE} compacting older history ({level})")


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

"""Which model a run uses, and remembering what the user picked.

axiom carries no model name of its own. A run's model comes from what the user
named, what they last picked here, or what the host reports - and when none of
those settles it, the user is asked. This module owns everything except the
asking, which belongs to `terminal`.

Nothing here prints and nothing here reads input. `choose()` returns a decision
describing what happened and what, if anything, still needs a question; the
chat loop turns that into words.
"""

import json
from dataclasses import dataclass
from pathlib import Path

# Beside `.axiom/mcp.json`, and deliberately a separate file. `mcp.json` is
# written by the user and designed to be committed - the `${NAME}` substitution
# exists to make that safe. This one is written by axiom, is about one person's
# habit on one machine, and belongs in `.gitignore`.
DEFAULT_CHOICE_FILE = Path(".axiom") / "model.json"


def _where(path: "Path | None") -> Path:
    """The choice file to use, resolved when asked rather than at import.

    Every entry point takes `path=None` and comes through here, so the location
    is read from the module at call time. A default argument would freeze it
    at import and there would be no way to point a test somewhere harmless -
    which matters more than usual here, because the path is relative to the
    working directory and the working directory during a test run is this
    repository.
    """
    return DEFAULT_CHOICE_FILE if path is None else path


@dataclass(frozen=True)
class Decision:
    """How a run's model was settled, and what is left to ask.

    `model` is None only when the user still has to pick. Every other field is
    something the user is told, which is what keeps AC 22 true: a run never
    continues on a model nobody saw chosen.
    """

    model: str | None
    installed: tuple[str, ...] = ()
    # The entry a bare enter accepts. None when there is nothing to ask.
    default: str | None = None
    # Named but not installed. The user hears this before anything else.
    missing: str | None = None
    # The remembered choice has been removed from the host since it was made.
    forgotten: str | None = None
    # Settled without asking, and why - so the reason can be said out loud.
    reason: str = ""


def sorted_models(names: list[str]) -> tuple[str, ...]:
    """The host's models in an order that does not move under the user.

    Ollama returns them newest-modified first, so pulling anything renumbers
    the list and a user picking "2" from memory gets a different model than
    they did yesterday. Sorting by name is what makes a number mean something
    across runs (AC 6). Case-insensitive, so `Qwen` and `qwen` do not split
    the ordering, with the name itself breaking ties so the sort is total.
    """
    return tuple(sorted(names, key=lambda name: (name.lower(), name)))


def read_choice(host: str, path: Path | None = None) -> str | None:
    """The model last picked for this host, or None.

    Every failure is None. A file that is missing, unreadable, not JSON, not an
    object, or holding something that is not a string for this host all mean
    the same thing to the caller - nothing has been chosen here yet - and none
    of them is worth ending a session over (AC 33).
    """
    path = _where(path)
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(document, dict):
        return None
    remembered = document.get(host)
    return remembered if isinstance(remembered, str) else None


def unreadable(path: Path | None = None) -> bool:
    """Whether a choice file exists but cannot be used.

    Kept apart from `read_choice` returning None, because the two are different
    things to say. No file at all is the ordinary first run and deserves
    silence; a file that is there and broken is worth one line, or the user
    edits it, sees no effect, and has no idea why (AC 33).
    """
    path = _where(path)
    if not path.is_file():
        return False
    try:
        return not isinstance(json.loads(path.read_text(encoding="utf-8")), dict)
    except (OSError, ValueError):
        return True


def write_choice(model: str, host: str, path: Path | None = None) -> str | None:
    """Remember `model` for `host`. Returns a problem, or None on success.

    Returns rather than raises, the same way `config.read_servers` does: a
    choice that cannot be saved costs the *remembering*, never the session
    (AC 34). The user picked a model and they get it either way.

    Other hosts' entries are preserved, and a file that cannot be parsed is
    replaced rather than aborted over - it holds only a preference, and
    refusing to save because a previous save is corrupt would strand the user
    with no way back except deleting a file nobody told them about.
    """
    path = _where(path)
    document = {}
    if path.is_file():
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(existing, dict):
                document = existing
        except (OSError, ValueError):
            document = {}
    document[host] = model
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    except OSError as refused:
        return f"could not remember this choice ({refused})"
    return None


def choose(
    named: str | None,
    installed: list[str],
    host: str,
    interactive: bool,
    path: Path | None = None,
) -> Decision:
    """Settle the run's model, or say what has to be asked.

    The order is fixed and each step is a criterion:

    - A named model that is installed wins outright, with no list (AC 16).
    - A named model the host does not have is reported, then treated exactly as
      though nothing had been named (AC 20, AC 21). It is never substituted
      silently, and the substitute is never chosen without saying so.
    - One model installed is chosen without a question (AC 17).
    - Not a terminal means never asking: the remembered choice if the host
      still has it, else the first model (AC 18, AC 19).
    - Otherwise the user is asked, with the remembered choice marked, or the
      first model when there is nothing remembered or what was remembered has
      gone (AC 9, AC 10, AC 11, AC 15).

    `installed` is assumed non-empty - an empty host is a fatal condition the
    caller reports and exits on (AC 32), not a decision to be made here.
    """
    available = sorted_models(installed)
    missing = None
    if named is not None:
        if named in available:
            return Decision(named, available, reason="named")
        missing = named

    remembered = read_choice(host, path)
    forgotten = remembered if remembered and remembered not in available else None
    preferred = remembered if remembered in available else None

    if len(available) == 1:
        return Decision(
            available[0], available, missing=missing, forgotten=forgotten, reason="only"
        )

    if not interactive:
        return Decision(
            preferred or available[0],
            available,
            missing=missing,
            forgotten=forgotten,
            reason="remembered" if preferred else "first",
        )

    return Decision(
        None,
        available,
        default=preferred or available[0],
        missing=missing,
        forgotten=forgotten,
    )


def picked(entry: str, available: tuple[str, ...], default: str | None) -> str | None:
    """The model an answer to the list names, or None if it names none.

    An empty line takes the marked default, which is what makes a bare enter
    work (AC 9). Whitespace counts as empty - a line of spaces is a user
    pressing enter, not an attempt to name something.

    Only a number is accepted here. A name is #49's business at the switch
    prompt; at startup the list is the only thing on offer, and accepting names
    too would make "3" ambiguous the day someone installs a model called 3.
    """
    answer = entry.strip()
    if not answer:
        return default
    if not answer.isdigit():
        return None
    index = int(answer)
    if not 1 <= index <= len(available):
        return None
    return available[index - 1]

"""Where the blank lines go, so a conversation reads as blocks.

The whole story is about *placement*, so every test here asserts on the shape
of the captured output rather than on any word in it. AC 11 - that no word
changed - is the golden transcript's job, and it holds: regenerating it moved
blank lines and nothing else.

One thing to keep in mind reading these. `feed` prints the prompt but does not
echo what the user typed, so a turn appears here as `> ` alone where a real
terminal shows `> hello` and the newline the user's own Enter produced. The
gap is the same either way - it is the newline `start_turn` adds *after* that
one.
"""

import pytest

from axiom import main
from axiom.backend import Call
from conftest import StubBackend, feed


def run(capsys, monkeypatch, typed, **stub):
    stub.setdefault("models", ["a:1b"])
    monkeypatch.setattr("sys.stdin.isatty", lambda: False)
    made = StubBackend(**stub)
    feed(monkeypatch, [*typed, "/exit"])
    main([], using=made)
    out = capsys.readouterr()
    # Everything after the startup lines - the conversation itself.
    return out.out[out.out.index("> ") :], out


def test_a_turn_is_followed_by_a_blank_line(capsys, monkeypatch):
    """AC 2. Without this the next prompt sits under the last line of the answer."""
    body, _ = run(capsys, monkeypatch, ["hello"])

    assert body.startswith("> \na reply\n\n> ")


def test_a_turn_is_preceded_by_a_blank_line(capsys, monkeypatch):
    """AC 1.

    In a real terminal the user's Enter ends the prompt line and this newline
    makes the gap under it. Here there is no echo, so the assertion is that
    `start_turn` puts a newline between the prompt and the first thing said
    back - which is the same newline.
    """
    body, _ = run(capsys, monkeypatch, ["hello"])

    assert body.index("\n") < body.index("a reply")


def test_several_turns_each_read_as_one_block(capsys, monkeypatch):
    """AC 3."""
    body, _ = run(capsys, monkeypatch, ["one", "two", "three"])

    assert body.count("\n\n") == 3


def test_a_turn_that_calls_tools_stays_one_block(capsys, monkeypatch):
    """AC 4, AC 5. The call, its result and the answer belong together.

    The temptation is a gap around each tool call, which would break one turn
    into pieces that look like separate turns.
    """
    body, _ = run(
        capsys,
        monkeypatch,
        ["read it"],
        turns=[[Call("read_file", {"path": "x.txt"})], ["done"]],
    )

    turn = body[: body.rindex("\n\n")]
    assert "read_file" in turn
    assert "  | " in turn
    assert "\n\n" not in turn, "the turn was broken into more than one block"


def test_a_compaction_notice_belongs_to_the_turn_that_caused_it(capsys, monkeypatch):
    """AC 5. It is axiom talking about this turn, not a turn of its own."""
    # Big enough to hold the standing prompt - a window under about 250 tokens
    # refuses every turn instead of compacting, and nothing is ever said.
    body, _ = run(
        capsys,
        monkeypatch,
        ["hello", "again"],
        info={"a.context_length": 1000},
        usage=900,
    )

    assert "compacting" in body
    for block in [b for b in body.split("\n\n") if "compacting" in b]:
        assert "a reply" in block, "the notice was left in a block of its own"


def test_an_empty_line_adds_no_gap(capsys, monkeypatch):
    """AC 7. Nothing happened, so nothing is separated."""
    body, _ = run(capsys, monkeypatch, ["", "", "hello"])

    assert body.startswith("> > > \na reply")


def test_a_model_command_leaves_no_stray_blank(capsys, monkeypatch):
    """AC 8. A command is not a turn."""
    body, _ = run(capsys, monkeypatch, ["/model a:1b"], models=["a:1b", "b:2b"])

    assert "\n\n" not in body, "a command that ran no turn left a gap behind"


def test_a_failed_turn_is_separated_like_any_other(capsys, monkeypatch):
    """AC 9."""
    body, out = run(capsys, monkeypatch, ["hello"], turns=[[KeyboardInterrupt()]])

    assert body.endswith("\n\n> ")
    assert "cancelled" in out.err


def test_a_refused_turn_is_separated_like_any_other(capsys, monkeypatch):
    """AC 9. A message too large never reaches the model, and still gets its gap."""
    # A window that holds the standing prompt comfortably, and a message that
    # cannot fit in it - so this is the "message too large" path rather than
    # the "cannot hold even an empty message" one, which is a different exit
    # and would prove a different criterion.
    body, out = run(capsys, monkeypatch, ["x" * 20000], info={"a.context_length": 1000})

    assert body.endswith("\n\n> ")
    assert "too large to send" in out.err


@pytest.mark.parametrize("typed", [["hello"], ["", "hello"], ["hello", "again"]])
def test_no_gap_is_ever_doubled(capsys, monkeypatch, typed):
    """AC 10."""
    body, _ = run(capsys, monkeypatch, typed)

    assert "\n\n\n" not in body


def test_startup_is_one_block_with_a_gap_before_the_first_prompt(capsys, monkeypatch):
    """AC 6. Said once, together, and then the conversation starts."""
    monkeypatch.setattr("sys.stdin.isatty", lambda: False)
    feed(monkeypatch, ["/exit"])
    main([], using=StubBackend(models=["a:1b"]))
    printed = capsys.readouterr().out

    startup = printed[: printed.index("> ")]
    assert "\n\n" not in startup, "startup was broken into blocks"
    # How *many* lines startup says is not this criterion's business - #61 added
    # one and #58 AC 6 was never about the count. What matters is that they
    # arrive as one block with nothing blank inside it.
    assert startup.count("\n") >= 2, "startup said less than it should"
    assert startup.strip(), "startup said nothing at all"

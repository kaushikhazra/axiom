"""What a bounded summary holds, and what goes when it fills.

**Read the cycle-1 log before trusting this file.** Most of #62's criteria are
about what a *model* produces, and `StubBackend.complete` returns whatever the
test told it to. A test asserting the summary holds the right things, against a
stub that was told what to return, proves only that the stub was told.

So the split here is deliberate and stated per test:

- `bounded()` is settled by tests. It is deterministic and takes no model.
- The honesty and the bound - AC 6, AC 7, AC 8 - are settled by tests.
- Recall across compactions - AC 9, AC 10 - is settled by tests, with a stub
  returning a summary the test wrote.
- **AC 4 and AC 5 are settled by a live probe**, recorded in `logs/cycle-1.md`
  with real output and a six-run measurement. Nothing here can prove them, and
  the instruction assertions below are evidence of *intent*, not of effect.
"""

import pytest

from axiom import compaction
from conftest import StubBackend, feed, history


# --- The instruction says what it should (intent, not effect) -----------


def test_the_instruction_asks_for_provenance_not_importance():
    """AC 4, as intent only.

    An instruction is a request. Measured against two models, this one is
    honoured by `gemma4:e2b` - general knowledge fell from 5.0 bullets to 0.7
    over six runs - and largely ignored by `qwen2.5:7b`, where the difference
    sat inside the run-to-run noise. That measurement is the evidence for
    AC 4; this test only pins that the request is still being made.
    """
    text = compaction.COMPACTION_INSTRUCTION.lower()

    assert "would still be true if this conversation had never happened" in text
    assert "where a fact came from, not about how important it is" in text


def test_the_instruction_allows_an_empty_answer():
    """AC 11, as intent only.

    Measured: `gemma4:e2b` returns nothing for five runs of six on pure
    pleasantries, against four bullets every time before. `qwen2.5:7b` is
    unmoved at 4.7. The numbers are the evidence; this pins the request.
    """
    text = compaction.COMPACTION_INSTRUCTION.lower()

    assert "nothing at all" in text
    assert "empty answer is correct" in text


def test_the_summariser_is_shown_the_turns_it_must_not_repeat():
    """AC 5, structurally - and this part *is* testable.

    `compact` could not avoid duplicating the kept turns because it was never
    given them. Whether a model then honours it is measured separately; that
    it is now *possible* is not a matter of opinion.
    """
    asked = StubBackend(summary="x")
    compaction.compact(
        asked,
        "m",
        [{"role": "user", "content": "the deadline is the 14th"}],
        kept=[{"role": "assistant", "content": "Your deadline is the 14th."}],
    )

    sent = asked.completed[-1][0]["content"]
    assert "do not repeat them" in sent
    assert "Your deadline is the 14th." in sent
    assert "TURNS TO SUMMARISE" in sent


def test_nothing_extra_is_sent_when_there_are_no_kept_turns():
    """AC 5's cost. The second copy is only paid when it can buy something."""
    asked = StubBackend(summary="x")
    compaction.compact(asked, "m", [{"role": "user", "content": "hello"}])

    sent = asked.completed[-1][0]["content"]
    assert "TURNS BEING KEPT" not in sent
    assert "TURNS TO SUMMARISE" not in sent


def test_the_instruction_still_forbids_ranking_by_importance():
    """AC 12, and a guard on #32.

    #32 added that sentence after oldest-first dropping lost "my cat is called
    Biscuit" from turn one. Provenance and importance are different axes, and
    a later edit that conflates them would re-open a measured bug.
    """
    text = compaction.COMPACTION_INSTRUCTION.lower()

    assert "do not judge some facts as more important than others" in text
    assert "brief, early" in text


# --- What goes when it fills --------------------------------------------


def summary(*facts: str) -> str:
    return "\n".join(["Summary of earlier conversation:", *facts])


def test_the_earliest_facts_are_kept(capsys):
    """AC 3, as #32 settled it: the middle goes, not the oldest.

    Identity-shaped facts are stated once and stay relevant; recent ones are
    live context. What can be spared is between them.
    """
    facts = [f"- fact {n}" for n in range(12)]
    kept, dropped = compaction.bounded(summary(*facts), limit=120)

    assert "- fact 0" in kept
    assert dropped, "nothing was dropped, so this proves nothing"
    assert "- fact 0" not in dropped


def test_what_is_dropped_is_named_one_by_one(capsys):
    """AC 6. #32's promise, and it must survive this row untouched."""
    facts = [f"- fact {n}" for n in range(12)]
    _, dropped = compaction.bounded(summary(*facts), limit=120)

    from axiom import terminal

    terminal.note_facts_forgotten(dropped)
    printed = capsys.readouterr().out

    for fact in dropped:
        assert fact in printed, "a fact went without being named"


def test_a_summary_with_room_to_spare_drops_nothing():
    """AC 8."""
    kept, dropped = compaction.bounded(summary("- one", "- two"), limit=10_000)

    assert dropped == []
    assert "- one" in kept and "- two" in kept


def test_the_bound_is_still_enforced():
    """AC 7. The limit is unchanged and still cuts."""
    facts = [f"- a fact number {n} with some length to it" for n in range(40)]
    kept, dropped = compaction.bounded(summary(*facts), limit=300)

    assert len(kept) <= 300
    assert dropped


def test_the_fraction_of_the_window_is_unchanged():
    """AC 7. Half the window, as #32 set it."""
    assert compaction.SUMMARY_FRACTION == 0.5
    assert compaction.summary_limit(2000) == int(
        2000 * 0.5 * compaction.SAFE_CHARS_PER_TOKEN
    )


def test_an_empty_summary_survives_bounding():
    """AC 11, the half a test can settle: axiom invents nothing of its own."""
    kept, dropped = compaction.bounded("", limit=100)

    assert kept == ""
    assert dropped == []


def test_a_model_that_returns_nothing_yields_no_summary():
    """AC 11, the other half a test can settle.

    Whether a *model* invents facts from small talk is a live question and is
    recorded in the cycle log. What axiom must not do is manufacture one when
    the model said nothing.
    """
    assert (
        compaction.compact(
            StubBackend(summary=""), "m", [{"role": "user", "content": "hi"}]
        )
        == ""
    )


# --- Recall across compaction -------------------------------------------


def test_a_fact_given_before_a_compaction_survives_it(capsys, monkeypatch):
    """AC 9, with a stub returning a summary the test wrote.

    This proves the *carrying*, not the summarising - the stub was told what
    to return. What it rules out is a compaction that drops the summary on the
    floor.
    """
    backend = StubBackend(
        info={"a.context_length": 1000},
        usage=900,
        summary="Summary of earlier conversation:\n- the car registration is WB-24-9931",
        models=["a:1b"],
    )
    monkeypatch.setattr("sys.stdin.isatty", lambda: False)
    feed(monkeypatch, ["one", "two", "three", "/exit"])

    from axiom import main

    main([], using=backend)

    assert backend.completed, "no compaction ran, so this proves nothing"
    carried = history(backend.streamed[-1])
    assert any("WB-24-9931" in (m.get("content") or "") for m in carried)


def test_two_compactions_do_not_lose_what_the_first_kept(capsys, monkeypatch):
    """AC 10."""
    backend = StubBackend(
        info={"a.context_length": 1000},
        usage=900,
        summary="Summary of earlier conversation:\n- the car registration is WB-24-9931",
        models=["a:1b"],
    )
    monkeypatch.setattr("sys.stdin.isatty", lambda: False)
    feed(monkeypatch, ["one", "two", "three", "four", "five", "/exit"])

    from axiom import main

    main([], using=backend)

    assert len(backend.completed) >= 2, "fewer than two compactions ran"
    carried = history(backend.streamed[-1])
    assert any("WB-24-9931" in (m.get("content") or "") for m in carried)


@pytest.mark.parametrize("limit", [50, 120, 400, 10_000])
def test_bounding_never_loses_the_header(limit):
    """AC 12. The header is what marks a summary as a summary to `compaction`."""
    facts = [f"- fact {n}" for n in range(20)]
    kept, _ = compaction.bounded(summary(*facts), limit=limit)

    assert kept.splitlines()[0] == "Summary of earlier conversation:"

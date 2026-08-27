"""#42: a session survives a turn refused for being too large.

The size check decides whether to send at all. Before #42 it refused and the
turn was dropped with nothing after it, so a session could reach a state where
every message was refused and nothing said that retrying was pointless.
"""

import axiom
from axiom import compaction, terminal
from conftest import StubBackend, feed

# The system prompt is a fixed cost the user cannot shorten and compaction
# cannot forget. Measured at scaffold time; derived here so the tests do not
# go stale when the prompt is reworded.
PROMPT_TOKENS = len(axiom.tools.system_prompt(axiom.tools.Limits())) // 3


class Watched(StubBackend):
    """Records how many times compaction actually ran."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.compactions = 0

    def complete(self, model, messages):  # noqa: ANN001
        self.compactions += 1
        return super().complete(model, messages)


def long_message(times: int = 60) -> str:
    return "please consider " + "a lengthy matter " * times


# --- AC 1 and AC 2: compaction runs because of the size ---------------------


def test_a_payload_too_large_compacts_whatever_usage_said(monkeypatch, capsys):
    """AC 1.

    Measured before the fix: a turn refused at 287 tokens over while a
    compaction from 1939 tokens to 226 - against a 2000 context - went
    unattempted, because the *previous* turn's usage sat 50 tokens under the
    trigger. An eightfold reduction, available and unused.
    """
    context = 2000
    under_the_trigger = int(context * compaction.COMPACTION_TRIGGER_FRACTION) - 50
    backend = Watched(
        info={"qwen2.context_length": context},
        usage=under_the_trigger,
        summary="- the user asked several things",
    )
    feed(monkeypatch, [long_message()] * 6 + ["/exit"])

    axiom.main([], using=backend)
    err = capsys.readouterr().err

    assert backend.compactions >= 1, "compaction never ran"
    assert "too large" not in err, "refused when compaction would have rescued it"
    assert len(backend.streamed) == 6, "a turn never reached the model"


def test_compaction_runs_on_a_first_turn_where_usage_is_none(monkeypatch, capsys):
    """AC 1: "whatever the previous turn's reported usage was".

    On the first turn of a session there is no previous turn, so `running_usage`
    is None and `maybe_compact` declines outright. The size check has to be able
    to trigger compaction on its own.
    """
    backend = Watched(info={"qwen2.context_length": 2000}, usage=1)
    feed(monkeypatch, [long_message(200), long_message(200), "/exit"])

    axiom.main([], using=backend)
    capsys.readouterr()

    assert backend.compactions >= 1


def test_nothing_is_refused_before_compaction_has_run(monkeypatch, capsys):
    """AC 2: ordering, not wording.

    A refusal that happens before compaction has been given its turn fails
    this however well it reads.
    """
    backend = Watched(
        info={"qwen2.context_length": 2000}, usage=1, summary="- one small fact"
    )
    feed(monkeypatch, [long_message()] * 5 + ["/exit"])

    axiom.main([], using=backend)
    err = capsys.readouterr().err

    if "too large" in err:
        assert backend.compactions >= 1, "refused without compacting first"


def test_the_message_the_user_just_typed_is_never_compacted_away(monkeypatch, capsys):
    """The bug cycle 3 found by attacking AC 3, and the worst one in this issue.

    `maybe_compact` runs *before* the user's line is appended, which is what
    keeps compaction to history. `compact_to_fit` runs after it, so the new
    message was itself a compaction candidate - and at `kept_pairs=0` it was
    replaced by a summary of itself. The model received the system prompt and
    "Summary of earlier conversation: - the user asked a long question", with
    no user message at all, and answered a question it had never seen. Nothing
    was said about it. That is worse than the refusal it replaced.
    """
    marker = "WHAT-IS-THE-CAPITAL-OF-PERU"
    question = marker + " " + ("and here is a great deal more detail " * 90)
    backend = Watched(
        info={"qwen2.context_length": 1200},
        usage=1,
        summary="- the user asked a long question",
    )
    feed(monkeypatch, [question, "/exit"])

    axiom.main([], using=backend)
    err = capsys.readouterr().err

    for sent in backend.streamed:
        assert any(marker in (m.get("content") or "") for m in sent), (
            "the model was sent a turn without the question it was meant to answer"
        )
    # Too large to send at all here, which is the honest outcome - and the
    # advice is one the user can act on.
    assert "this message is about" in err
    assert "shorter" in err


def test_history_behind_the_new_message_is_still_compacted(monkeypatch, capsys):
    """The other half: holding the message out must not stop compaction working.

    A fix that simply skipped compaction whenever a message was pending would
    pass the test above and undo the whole issue.
    """
    backend = Watched(
        info={"qwen2.context_length": 2000},
        usage=1,
        summary="- the user asked several long things",
    )
    feed(monkeypatch, [long_message(200)] * 5 + ["a short follow-up", "/exit"])

    axiom.main([], using=backend)
    err = capsys.readouterr().err

    assert backend.compactions >= 1, "history behind the message was never compacted"
    assert "too large" not in err
    assert len(backend.streamed) == 6


# --- AC 3 and AC 4: the session carries on ----------------------------------


def test_a_following_turn_is_not_refused_for_the_same_reason(monkeypatch, capsys):
    """AC 3.

    Whatever compaction achieved must be kept when the turn is rolled back, or
    the next turn starts from the same oversized history and meets the wall
    again.
    """
    context = 1200
    backend = Watched(
        info={"qwen2.context_length": context},
        usage=1,
        summary="- a short fact",
    )
    # One message too large on its own, then an ordinary one.
    feed(monkeypatch, ["x" * (context * 3), "and now something short", "/exit"])

    axiom.main([], using=backend)
    out, err = capsys.readouterr().out, capsys.readouterr().err

    assert err.count("too large") <= 1, "the second turn was refused too"
    assert len(backend.streamed) >= 1, "the session never recovered"


def test_a_short_message_is_never_refused_when_the_context_allows_one(
    monkeypatch, capsys
):
    """AC 4: no state where every message, however short, is refused."""
    context = 1200
    backend = Watched(info={"qwen2.context_length": context}, usage=1)
    feed(monkeypatch, ["x" * (context * 3), "hi", "hi", "hi", "/exit"])

    axiom.main([], using=backend)
    err = capsys.readouterr().err

    assert err.count("too large") <= 1, "short messages kept being refused"


def test_a_session_at_the_wall_lets_the_summary_go_and_carries_on(monkeypatch, capsys):
    """AC 4, in the band cycle 3 found it broken.

    Context above the floor but below roughly twice it. Before this: four turns
    worked, then four consecutive refusals of 80-character messages, each
    preceded by a re-compaction that achieved nothing. That is exactly "a state
    where every message, however short, is refused".
    """
    backend = Watched(
        info={"qwen2.context_length": 350},
        usage=1,
        summary="\n".join(f"- fact {n} the user mentioned earlier" for n in range(30)),
    )
    feed(monkeypatch, ["please tell me a little more about that " * 2] * 10 + ["/exit"])

    axiom.main([], using=backend)
    out, err = capsys.readouterr()

    assert err == "", "the session still refuses"
    assert out.count("a reply") == 10, "not every message was answered"


def test_the_facts_let_go_are_named_one_by_one(monkeypatch, capsys):
    """AC 4 and AC 8 together.

    This path drops more at once than any other, which makes saying so more
    important rather than less. #32 exists because a long session must never
    lose information silently.
    """
    backend = Watched(
        info={"qwen2.context_length": 350},
        usage=1,
        summary="\n".join(f"- fact {n} the user mentioned earlier" for n in range(30)),
    )
    feed(monkeypatch, ["please tell me a little more about that " * 2] * 10 + ["/exit"])

    axiom.main([], using=backend)
    out = capsys.readouterr().out

    assert "the summary is full - forgetting" in out
    assert "- fact 29 the user mentioned earlier" in out, "facts went unnamed"


def test_history_is_not_thrown_away_when_the_message_is_the_problem(
    monkeypatch, capsys
):
    """The cold check on the fix itself.

    If the message the user just typed is what will not fit, dropping the
    conversation buys nothing and costs everything. The last resort only fires
    when an empty history would actually fit.
    """
    backend = Watched(
        info={"qwen2.context_length": 1200},
        usage=1,
        summary="- the user's cat is called Biscuit",
    )
    feed(
        monkeypatch,
        ["my cat is called Biscuit", "x" * 6000, "what is my cat called?", "/exit"],
    )

    axiom.main([], using=backend)
    out, err = capsys.readouterr()

    assert "this message is about" in err, (
        "the oversized message was not the reported cause"
    )
    last = backend.streamed[-1]
    assert any("Biscuit" in (m.get("content") or "") for m in last), (
        "the conversation was thrown away over a message that was too large"
    )


def test_a_comfortable_session_never_drops_its_summary(monkeypatch, capsys):
    """The negative. This path fires only when the ladder is exhausted."""
    backend = Watched(info={"qwen2.context_length": 32768}, usage=1)
    feed(monkeypatch, ["hello", "and another thing", "/exit"])

    axiom.main([], using=backend)
    out = capsys.readouterr().out

    assert "forgetting" not in out
    assert backend.compactions == 0


# --- AC 5 and AC 6: what the user is told -----------------------------------


def test_the_three_causes_are_told_apart():
    """AC 5, at the seam.

    Three different things can be over, and only one of the three suggestions
    would ever help in each case.
    """
    overhead = PROMPT_TOKENS * 3  # characters
    assert (
        compaction.what_will_not_fit("hi", PROMPT_TOKENS // 2, overhead)
        == compaction.CANNOT_CONTINUE
    )
    assert (
        compaction.what_will_not_fit("x" * 9000, PROMPT_TOKENS + 100, overhead)
        == compaction.MESSAGE_TOO_LARGE
    )
    assert (
        compaction.what_will_not_fit("hi", PROMPT_TOKENS + 100, overhead)
        == compaction.CONVERSATION_TOO_LARGE
    )


def test_each_cause_gets_its_own_message_and_its_own_advice(capsys):
    """AC 5: the message names what is actually too large.

    Before #42 all three said "try a shorter message, or start a new session".
    Cycle 1 watched the overage stop falling at 5 tokens while the message
    shrank to a single character - advice to type less, where typing less could
    never work.
    """
    said = {}
    for cause in ("message", "conversation", "cannot-continue"):
        terminal.report_too_large(42, cause)
        said[cause] = capsys.readouterr().err

    assert len({*said.values()}) == 3, "two causes share a message"
    assert "shorter" in said["message"]
    assert "shorter" not in said["conversation"], "advice that cannot be taken"
    assert "new session" in said["conversation"]
    assert "cannot hold even an empty message" in said["cannot-continue"]
    assert "shorter" not in said["cannot-continue"]


def test_a_session_that_cannot_continue_offers_the_way_out(monkeypatch, capsys):
    """#42 AC 6, as amended by #49 AC 19.

    #42 ended the session here and was right to at the time: nothing the user
    could type would fit, so repeating the line at every prompt was the
    discovery-by-retrying it existed to prevent, and ending was what made #42
    AC 4 true - no state where every message is refused, because there are no
    more messages.

    `/model` changes the premise. The window belongs to the model, and a switch
    keeps the conversation, so the wall is now escapable without losing
    anything. The line therefore names the model that cannot hold it and the
    command that fixes it, and the session stays. #42 AC 4's protection
    survives in a better form: there is a way out that is not "type less".
    """
    backend = Watched(info={"qwen2.context_length": PROMPT_TOKENS // 2}, usage=1)
    feed(monkeypatch, ["hello", "hi", "?", "a", "/exit"])

    axiom.main([], using=backend)
    err = capsys.readouterr().err

    assert "/model" in err, "a wall with no way through it"
    assert "qwen2.5:7b" in err, "does not name the model that cannot hold it"
    assert backend.compactions == 0, "compacted a session nothing can save"
    assert len(backend.streamed) == 0, "sent a payload that cannot fit"


def test_a_session_that_cannot_continue_still_accepts_a_switch(monkeypatch, capsys):
    """#49 AC 19. The session stays usable, and the way out really works."""
    backend = Watched(
        info={"qwen2.context_length": PROMPT_TOKENS // 2},
        usage=1,
        models=["big:70b", "qwen2.5:7b"],
    )
    feed(monkeypatch, ["hello", "/model", "1", "/exit"])

    axiom.main([], using=backend)

    # Reached the list rather than having ended four lines earlier.
    assert "models on" in capsys.readouterr().out


# --- AC 7 and AC 8: unchanged, and honest about forgetting ------------------


def test_a_turn_that_fits_is_untouched(monkeypatch, capsys):
    """AC 7: no extra compaction, no extra output."""
    backend = Watched(info={"qwen2.context_length": 32768}, usage=1)
    feed(monkeypatch, ["hello", "and another thing", "/exit"])

    axiom.main([], using=backend)
    out, err = capsys.readouterr().out, capsys.readouterr().err

    assert backend.compactions == 0
    assert err == ""
    assert "compacting" not in out
    assert "too large" not in out


def test_a_size_triggered_compaction_reports_the_way_a_usage_one_does(
    monkeypatch, capsys
):
    """AC 8.

    #32 spent three cycles making compaction say what it let go. A second path
    that forgot silently would pass any size assertion and destroy that.
    """
    backend = Watched(
        info={"qwen2.context_length": 2000},
        usage=1,
        summary="\n".join(f"- fact {n} the user mentioned" for n in range(60)),
    )
    feed(monkeypatch, [long_message(200)] * 4 + ["/exit"])

    axiom.main([], using=backend)
    out = capsys.readouterr().out

    assert "compacting older history" in out, "compacted without saying so"


def test_a_planted_fact_survives_a_size_triggered_compaction(monkeypatch, capsys):
    """AC 8: preserves facts, not just size.

    Asserted on what the model was actually sent, which is the only place the
    fact either survived or did not.
    """
    backend = Watched(
        info={"qwen2.context_length": 2000},
        usage=1,
        summary="- the user's cat is called Biscuit",
    )
    feed(monkeypatch, ["my cat is called Biscuit", *[long_message(200)] * 4, "/exit"])

    axiom.main([], using=backend)
    capsys.readouterr()

    last = backend.streamed[-1]
    assert any("Biscuit" in (m.get("content") or "") for m in last), (
        "the planted fact was lost by the size-triggered compaction"
    )

# Cycle 10 — converged, and two of the last four moves were retractions

2026-09-02, 01:52–02:05 +0530. Branch `feature/80-multiline`. Row 18 of the queue.

## The measurement

**All 21 criteria a test can reach are met, each proved by a break watched going red.**
Fifteen are a person's. 21 + 15 = 36, and neither number is ever added to the other.

| bucket | count | criteria |
|---|---|---|
| **1 — met, proved by a break** | **21** | 5, 11, 13, 14, 15, 16, 17, 19, 20, 21, 22, 23, 28, 29, 30, 31, 32, 33, 34, 35, 36 |
| 2 — implemented, not proved | 0 | — |
| 3 — not started | 0 | — |
| **a person's, not the loop's** | 15 | 1, 2, 3, 4, 6, 7, 8, 9, 10, 12, 18, 24, 25, 26, 27 |

Four moved: **21, 27, 34, 35** — and **AC 6** was decided. Two of those five are the loop
taking something back rather than adding to it, which is the honest shape of a last cycle.

## AC 21 needed nothing built, and that was the finding

The trap the action file warned about — *a half-built refusal looks like a feature* — did not
have to be walked into, because the refusal already exists. #42 built it: `too_large`,
`what_will_not_fit`, `report_too_large`, and `del messages[before:]`. **A paste is a long
`line` like any other.** Reusing that path is not laziness, it is the thing `_will_not_fit`'s
own docstring already argues for: a second refusal with its own arithmetic would disagree with
the first and refuse the same message twice with two different numbers.

It passed first time, which the queue's Standing says is exactly when to disbelieve it. Broken
two ways, both red:

- **the paste quietly cut to 100 characters and sent** — the #42 failure, and the one this
  criterion exists for. A refusal is visible; a truncation is not.
- **the refusal ending the session instead of the turn** — #42 AC 4 underneath #80 AC 21.

The test asserts the model was sent **nothing at all**, not that it was sent less. "Fewer than
N characters" would pass for exactly the implementation being guarded against.

## AC 27's test could not fail, and it had been counted for two cycles

    asked = sent_to(monkeypatch, capsys, "the message that survives")
    assert all("throw this away" not in message for message in asked)

**Nothing ever typed `"throw this away"`.** The test composed one message and asserted that a
string which appears nowhere in the suite was absent from it. It passed for every
implementation there is, including one that sent the abandoned buffer, and it would have gone
on passing forever.

Second vacuous test in two cycles, and the second of a different shape. Cycle 9's AC 17 was a
*count* satisfied by the feature doing nothing. This one is an assertion about a string that
does not exist — the same family as the queue's note on #60, where six tests asserted text was
*present in the byte stream* where the plain echo puts it regardless.

> **Ask what typed the string you are asserting about.** If nothing did, the assertion is
> about the absence of something that was never going to be there.

The criterion is real and cannot be reached: abandoning happens inside `compose`'s ctrl+c
binding, the buffer is cleared, and nothing leaves the reader. That is *why* AC 27 holds and
also why no test outside a session can see it. Test deleted, criterion moved to the manual
pass, and a comment left where it stood saying so.

## AC 34 and AC 35 said "status code" and asserted a string

Both criteria end *"with the same status code"*. Both tests asserted that `"an answer"` was
absent from the output — true of a stub with no turns whatever the exit path did. Now they
assert `main()` returns, which is what a status of 0 means here: the only non-zero code axiom
has is `CANNOT_START`, and it leaves as `SystemExit`. Broken by making the exit path
`sys.exit(CANNOT_START)`; both red.

**Three of the four criteria examined this cycle had tests that measured something adjacent to
what they claimed.** Not wrong about the behaviour — wrong about what the assertion could
detect.

## AC 6, decided rather than carried a third cycle

> On a terminal that cannot report ctrl+enter separately from enter, the user is still able to
> send a message of more than one line, and is told how.

**Decision: real, unimplemented, unverifiable here — kept in the issue and moved to the manual
pass unticked.**

- `assumption.md` records it as written by the agent rather than asked for.
- Kaushik's console reports ctrl+enter separately — measured, `0a` against `0d` — so the
  situation has never occurred on the only machine axiom runs on.
- It cannot be tested: a fallback lives in the key handling, and building a session is
  prohibited.

**Not struck, and that is the deliberate half.** Striking means renumbering thirty criteria,
and cycle 7 spent an entire cycle repairing eleven citations after the last renumbering. An
unticked row costs nothing. Revisit when axiom first runs where ctrl+enter arrives as a plain
carriage return — most Linux and macOS terminals — at which point it is an observed problem
with a reporter, not a guess.

## The citation instrument, third version and now correct

Cycle 9 found the narrow grep blind and widened it. **The wide one was wrong the other way**:
it cannot tell a claim from a disclaimer, so cycle 9's own note — *"this used to claim AC 4 and
AC 24 and never proved either"* — read as a claim to AC 4 and AC 24.

`.claude/loop/cited.py` replaces both. It parses the file and reads only the **first line** of
each test's docstring, which is the convention the tests already followed. It reported 21
claimed criteria against 21 targeted, and it found one more thing on the way: a docstring
citing `#42 AC 4` on its first line reported AC 4 as #80's. The convention gained the rule it
was missing — **a first line cites its own issue and nothing else** — and it lives in the
tool's docstring where the next reader meets it.

It is at `.claude/loop/` rather than in this iteration, because rows 19 and 20 need it too.

Also swept: `#80 AC 10` in `__init__.py`'s command guard, left behind by cycle 0's renumbering
and missed by cycle 7 because prose is not a citation. Now AC 13 and AC 14.

## The suite

    905 entering
    +3 added        AC 21 refused, AC 21 not shortened, AC 21 survivable
    -1 deleted      AC 27's vacuous test
    907 leaving     907 passed, 1 deselected, 78.76s

The arithmetic adds up. Wall clock flat against cycle 9's 79.44s.

`tests/baseline/transcript.txt` **unchanged**, fifteen cycles.

## Assumptions changed

None. The prohibition held: nothing added this cycle builds a session, and AC 21 — the last
unbuilt criterion — turned out to need no new code at all.

## Goal check

**Met**, on `loop.md`'s terms: 21 of 21 in bucket 1, suite green, baseline untouched, and
`manual-pass.md` carries all fifteen with what to do and what should happen.

**Not merged**, per `loop.md`. Fifteen criteria are unverified by anyone. That is not exit 3 —
nothing is blocked — it is a row finishing with work owed to a person.

## Handing over

Row 18 done. Row 19 — `76-indented-code` — scaffolded and running.

# Observe

Record each cycle:

- A status token for **every one of #60's 29 criteria**: `not-started` / `attempted` /
  `met-with-evidence` / `blocked`. All twenty-nine get a token every cycle, even "no change."
  Cite them as "AC 7".
- How far that moved from the last cycle, and what moved it.
- What is still missing, and whether it can be closed from here at all.
- Any assumption that changed.

## The three that decide whether this is any good

**AC 7 - a line that has been shown does not move again.** This rules out the obvious
implementation. `rich.Live` re-renders its whole renderable on every update, which on a reply
longer than the window is a scrolling smear. The shape that works is: commit finished lines,
redraw only the tail. **Test it by capturing the byte stream and asserting no line is emitted
twice and no cursor-up sequence appears** - not by looking at it and deciding it seems fine.

**AC 9 - an incomplete construct is never shown as complete.** A half-arrived `##` is not a
heading. In tension with AC 8, which forbids withholding text inside an unclosed fence. Getting
both is the actual work: show the characters, do not style them until the construct closes.

**AC 5 - every character reaches the screen.** The failure mode of markdown renderers is
silently eating what they do not understand. Assert it as a property: for a set of replies,
every non-markup character sent appears in the output. A renderer that drops content is worse
than no renderer.

## Where else this will be tempting to cheat

**AC 14, AC 15 - the piped path.** "Byte for byte as it is today" is measurable against the saved
transcript and against a redirected run. It is not "looks the same".

**AC 16 - history holds the reply as written, never as rendered.** Assert on the payload sent to
the model, not on the screen. A renderer that mutates what goes into `messages` would corrupt the
conversation invisibly.

**AC 20 - the hold-back survives.** `_could_still_be_a_call` withholds a reply while it might yet
be a bare-JSON tool call. Adding a renderer on top of conditional withholding is where a subtle
bug lives. Test a reply that turns out to be a call, and one that starts with `{` and turns out
to be prose.

**AC 28 - a rendering failure never costs the answer.** Force the renderer to raise and assert
the reply still appears in full, as plain text.

**AC 21 - an empty reply prints nothing and leaves no stray blank line.** #58 owns the spacing;
this must not disturb it.

## What counts as evidence

- **The captured byte stream**, for AC 7 and AC 9. Escape sequences are the evidence.
- **A live run against the local Ollama**, for the judgement Kaushik actually asked about: does
  it read better. Record a real reply before and after.
- **The golden transcript** for AC 14, AC 15, AC 29.
- **The payload** for AC 16.

## Standing checks

- **The full suite is re-run in every cycle that changes code**, and the result recorded. The
  baseline is **539 tests, green** at scaffold time, 2026-08-28 03:07 IST.
- **The suite must stay green with no Ollama running**, and must not be changeable by the
  environment:
  `env AXIOM_HOST=http://127.0.0.1:1 AXIOM_MODEL=nonsense:99b AXIOM_DEBUG_MAX_CONTEXT=7 uv run pytest -q`
- **The golden transcript should NOT change**, if AC 14 holds - tests capture non-terminal
  output, which stays plain. **If it changes, something is wrong rather than something is new.**
  Copy it aside in cycle 1 and check it at the end of every cycle.
- **Adding a dependency is this row's alone.** `rich` is the first since `mcp` in #43. Record the
  version pinned and why.
- **Ask whether each test could pass if the feature did nothing**, then break the feature and
  watch it go red. **Name the survivors**, one verdict each.
- If a criterion cannot be met as written, say so plainly and say why.

## The cycle that writes the code never declares it done

A separate cycle checks, reading the criteria from GitHub **before** the diff and before the
previous log. **Attack each criterion rather than confirming it.**

This has found something real in **eleven consecutive issues**. The shapes that recur, all live
here:

- **An assertion a wrong implementation also satisfies.** #61's AC 9 had *no* test at all while
  520 stayed green.
- **A default that happens to be right.** #56's `web=False`.
- **A test asserting more than its criterion**, which breaks when something correct lands. #61
  found two.
- **Single-sample conclusions.** #62 nearly adopted the wrong finding from three one-run probes.
  **This row has a judgement component - "does it read better" - and that is exactly where a
  single flattering sample is most tempting.**

## Goal check

- **Met** - all 29 criteria `met-with-evidence`, suite green and hermetic, transcript unchanged,
  a real before-and-after recorded.
- **Not met** - report which criteria moved and which did not, and write the next action.
- **Answer did not move** - report the flat result and stop. Do not run another variant.

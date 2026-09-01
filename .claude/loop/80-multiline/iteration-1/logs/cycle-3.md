# Cycle 3 — the reader, and two hours' worth of lesson in twenty minutes

2026-09-01, 21:26 +0530. Branch `feature/80-multiline`. Committed.

## The measurement

**Criteria demonstrably met: 2 of 36.** Moved by 1.

| bucket | count | criteria |
|---|---|---|
| **1 — met, proved by a break** | **2** | 3, 30 |
| 2 — **implemented but not proved** | 10 | 1, 2, 12, 13, 14, 18, 31, 32, 34, 35 |
| 3 — not started | 24 | 4–11, 15–17, 19–29, 33, 36 |

**AC 1, 2 and 18 work and are not counted.** The reader does what they ask -

    composed("one" + CTRL_ENTER + "two" + ENTER) == "one\\ntwo"

- and their tests are green. But their breaks did not run: two failed to apply
because the harness's search strings were mangled by escaping, and AC 18's break
(`multiline=False`) turned out not to violate the criterion at all - `insert_text`
puts a newline in the buffer either way, so the test stayed green **and was right to**.

A break that does not violate the criterion proves nothing about the test. So they stay in
bucket 2 and cycle 4 finishes them. Counting them would be the exact thing `observe.md`
exists to stop.

## The suite

    882 passed, 1 deselected, 86.95s     entering
    888 passed, 1 deselected, 84.24s     leaving

Arithmetic: 882 + 6 = 888. **Baseline untouched**, nine cycles across two issues.

## Fourteen tests died the moment the composer was wired

Not a regression - a collision that was always going to happen, and the shape is worth
keeping.

Those fourteen force `sys.stdout.isatty` **in order to exercise the renderer**, and supply
input through `builtins.input` like every other test. Wiring the composer put a real
prompt_toolkit session in their path, and it refuses to build against anything that is not a
real Windows console.

The fix is a `conftest` default: in tests, composing reads one line through `input`. That is
the behaviour those tests were written against, and it does not hide the feature from its
own tests, which drive `compose` directly with a pipe input.

**One test failed for a better reason and is worth naming.**
`test_forgetting_the_composing_reader_returns_to_the_real_one` was written in cycle 2
asserting the fallback was `builtins.input` - correct then, because no real composer
existed. Cycle 3 built one and the test **failed loudly rather than drifting**. Rewritten to
assert the same claim against the new truth.

## Two costs, both self-inflicted, both worth writing down

### A break that hangs is worse than a break that fails

With the accept binding broken, the reader waited for a key that never came. The harness hit
its own timeout, the run was killed, and **`finally` never restored the file** - leaving
`terminal.py` holding a break. Twice.

`subprocess.run(timeout=...)` does not help: it kills `uv` and leaves `pytest` holding the
pipes, so the harness blocks anyway.

**The fix belongs in the test, not the harness.** `create_pipe_input` can be closed, and a
closed pipe turns an unaccepted buffer into an EOF in milliseconds. A break now fails fast
instead of hanging, which is what a break is supposed to look like.

The general form: **anything a break can make wait forever must be given an end before the
break-proof runs.**

### The backslash rule earned its place again

`~/.claude/CLAUDE.md` and this repo's own memory both say it: a scripted replace containing a
backslash escape goes through the Edit tool. It cost two attempts here anyway -

- a docstring quoting `\\x0d` and `\\x0a` came out with **real** carriage returns in it,
  breaking the syntax
- the break harness's search strings did not match the source for the same reason

Both were written through a heredoc rather than Edit. The rule is not about being careful;
it is about not using that tool for that job.

## Breaks

| criterion | break | verdict |
|---|---|---|
| AC 3 | enter no longer sends | went red |
| AC 2 | ctrl+enter inserts nothing | **did not apply** |
| AC 1 | ctrl+enter sends instead of adding a line | **did not apply** |
| AC 18 | the buffer cannot hold more than one line | **stayed green - the break was wrong** |

## Assumptions changed

None. The binding measured by hand in `assumption.md` is what the reader implements, and
prompt_toolkit delivers it as cycle 1 predicted from its source.

## What only a person can confirm — unchanged

Criteria 2, 3, 4, 5, 7, 8, 9, 22, 23, 24. Note that **2 and 3 appear in both lists**: a pipe
input proves axiom does the right thing with the key, and only a person can confirm this
console sends it.

## Next

Finish AC 1, 2 and 18's breaks - through the Edit tool - and then AC 4, 5, 22 and 23, which
are what the user sees while composing.

# Cycle 5 — 2026-08-28 20:14 +0530

An experiment, reverted, and a decision that is now cheap to make. **Nothing was changed.**

## The one-line version works, and then does not

Adding `\s{4,}\S` to `_CONTAINED` - the whole change - was tried and measured before being
reverted.

**What it does:**

| | before | with the change |
|---|---|---|
| characters lost at width 40 | 41 | **0** |
| characters lost at width 60 | 25 | **0** |
| characters lost at width 200 | 0 | 0 |
| suite | 687 green | **687 green** |

It also leaves #73 alone, which `action.md` named as the boundary a careless regex would
break: `    - four spaces inside a list`, under `- Outer`, still renders as `◦ four spaces
inside a list` at depth 1 rather than as code. Checked, not assumed.

And the padding it leaves is **always width minus one** - measured at 20, 25, 30, 40, 41, 60,
80 and 120. It never reaches the window width, so it never costs the blank row that #60
AC 12 exists to prevent. That padding is Rich painting the block's background, which is also
what sets it apart from the prose around it.

**What it does not do:**

```
Here is the code:

' def total(values):                        '


'     return sum(values)                    '


' print(total([1,2]))                       '

That is it.
```

A three-line indented block comes out as **three separate blocks over eleven rows**. Ten
lines would be thirty. Each line is rendered alone, so each becomes its own code block with
its own spacing.

## Why that makes it a story rather than a regex

An indented code block has **no closing delimiter**. It ends when a line that is not indented
arrives - which a line-at-a-time renderer only learns *after* the block is over.

Fixing it properly means holding lines back until the block ends. Holding is barred for
everything but a table (#60 AC 8 and AC 10), and the table's exemption is recorded in the
source as a rule rather than a habit.

**So this is the same shape of problem as a table**, and it needs the same kind of decision:
a second construct allowed to be held, under the same rule that nothing held has ever been
shown. That is not something a loop should decide on its own, and it is not something a
one-line regex can deliver.

Written into `.tmp/issue-indented-code.md`, under the criteria, so whoever picks it up has
the measurement rather than the argument.

## What is left of this loop

**Nothing but a decision that is not mine.**

All 21 criteria of #72 hold, each with a test proven to fail when the fix is reverted or
correctly not break-sensitive. The suite is 687 and green. The loop's numeric condition -
characters lost at zero - is unmet only because of a construct that is not in #72, is not in
#73, and now has a drafted issue and a measured cost.

`action.md` said: *"If the answer is 'nothing but a decision that is not mine', say so and
stop rather than manufacturing work."* That is the answer.

## Goal check: NOT met, and stopping anyway

The goal says every criterion in #72, and `observe.md` adds characters lost at zero. The
first holds. The second cannot be closed inside this issue's scope without deciding a design
question that belongs to Kaushik.

**A loop that keeps running after its own question is answered is the failure this method
exists to avoid.** The fail-safe is 22:20 and there is nearly two hours left on it; this stops
short of that deliberately, with the reason recorded, which is what the method asks for when
a loop cannot converge on its own.

**The cron is deleted. The loop ends unconverged, and says why.**

## Suite

`uv run pytest` - **687 passed in 76.16s**, unchanged from cycle 4. The experiment was
reverted and green re-established before this was written.

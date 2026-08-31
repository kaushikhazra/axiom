# Action

All 21 criteria of #72 hold. The loop's other condition - characters lost at zero - does not,
because of `indented-code`: a four-space-indented line that is not a list item still loses 41
characters at width 40. It is not a criterion of #72 or #73, and #73 converged without it.

**This cycle does not decide whether to absorb it.** That is Kaushik's call, and the issue
is drafted at `.tmp/issue-indented-code.md` waiting for him. What this cycle can do is make
the decision cheap to act on either way.

1. **Measure the one-line version.** Adding `\s{4,}` to `_CONTAINED` would make an indented
   block wrap rather than crop, and would take characters lost to zero. Try it on a branch or
   in the working tree, run the probe at 40, 60 and 200, run the suite, and **record what it
   costs** - specifically whether an indented block still reads as set apart from prose once
   it wraps, and whether anything in the 687 goes red. Then revert it. The point is a
   measured answer sitting ready, not a change nobody asked for.
2. **Check the case #73 does cover still works** after any experiment: a four-space line
   *inside* a list is a list item at its own depth, not code. That is the boundary between
   the two behaviours and it is the thing a careless regex would break.
3. **Write down what is left of this loop honestly.** If the answer is "nothing but a
   decision that is not mine", say so and stop rather than manufacturing work - the fail-safe
   is 22:20 and a loop that keeps going after its own goal is answered is the failure this
   method exists to avoid.
4. `uv run pytest` - 687, green.

First thing to tackle: **the measured cost of the one-line version.** Kaushik will come back
to a choice between a new story and a one-token change, and the only thing that makes that
choice quick is knowing what the one-token change actually does.

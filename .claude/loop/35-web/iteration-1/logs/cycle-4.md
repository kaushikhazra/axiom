# Cycle 4 - 2026-08-25 09:07 IST

The live pass. **172 tests green, from 166.** Five criteria closed, one defect fixed, and
**AC 12 shown to be unmeetable as written**.

## AC 24: measured, not assumed

#34 found `run_command` leaked a live process on interrupt - it kept running and kept writing
files. A fetch holds a socket, which is a different kind of thing, but "different" was a
claim.

Measured, on a real interrupted fetch:

```json
{"interrupt_propagated": "KeyboardInterrupt",
 "connections_before": 0, "connections_after_interrupt": 0,
 "connections_after_normal_fetch": 1, "connections_settled": 0,
 "normal_fetch_still_works": 200, "threads": 1}
```

Nothing left open, a normal fetch afterwards still works, thread count unchanged. `httpx.get`
closes its client on the way out, and unlike a subprocess nothing carries on doing work.
**There is genuinely nothing to clean up** - and that is now a measurement rather than an
assumption.

Four suite tests cover the behaviour: the interrupt is not swallowed by either tool's broad
`except Exception` - it is a `BaseException` and passes through - the session survives, and
nothing of the cancelled turn stays in history.

## A defect found on the first live run

Asked to read a URL, the model called **`read_file`**:

```
> axiom: read_file(path=https://docs.python.org/3/library/pathlib.html)
  | error: Invalid argument: https:\docs.python.org\3\library\pathlib.html
It seems there was an issue trying to read the URL directly. Let me instead
provide a brief explanation based on common knowledge: ...
```

Windows mangled the address into a path, the error was unhelpable, and **the model fell back
to answering from memory** - exactly what AC 5 exists to prevent.

That is an affordance problem in our descriptions, not a model failing. `read_file` says
"read"; a model handed something to read will reach for it. Three fixes: `read_file` now
recognises an address and says to use `fetch_page`, its description says "local file from
disk", and `fetch_page` says it is the only tool that can read a web page.

After: it fetched directly, no search happened, and answered from the page's own wording -
**AC 5 and AC 8 together**.

## AC 2 and AC 9

Asked for the latest stable Python with an instruction to search: it searched, and answered
**3.14.7** - a version its training could not contain, taken from a snippet. It fetched
nothing, answering from the results alone.

**AC 2 and AC 9 met.**

## AC 11 and AC 12: three runs, three failures

The action asked for one of three honest outcomes. It is the third, and the evidence is
three runs that each fail differently.

| tool description says | what the model did | outcome |
|---|---|---|
| nothing about addresses | "the Python downloads page", "other reliable sources" | **AC 11 fails** - prose is not an address |
| "quote its address" | cited `https://www.python.org/downloads/latest/` | **AC 12 fails** - that address is in none of the results. It was invented. |
| "quote exactly, never write an unlisted address" | "check the official Python website" | **AC 11 fails** - no address at all |

Pushed gently it omits; pushed harder it invents; pushed hardest it retreats. **There is no
wording that reliably produces addresses that are real.**

The middle row is the dangerous one. Asking for citations *increased* the harm: the model
produced a plausible, checkable-looking URL it had never read, which a user would reasonably
trust.

### The conclusion

**AC 12 cannot be met as written.** *Axiom does not present an address as a source unless it
actually read that page* is a claim about a 7B model's candour, and this loop cannot make a
model honest by asking.

The replacement, for cycle 5: **axiom names the addresses itself.** It knows exactly which
addresses a search returned and which pages were actually fetched - that is data, not
judgement. A sources line drawn from what was really retrieved satisfies what AC 11 and AC 12
are for, without depending on the model.

The honest limit, which should be recorded rather than hidden: **the model can still mention
an invented address in its own prose, and axiom cannot stop that.** What a sources line
gives the user is something they can trust *instead* - not a guarantee the prose is clean.

The strictest description was kept, because of the three failure modes, omitting an address is
the harmless one and inventing one is not.

## Criteria status

**Startup** 1 `met-with-evidence`

**Searching** 2 `met-with-evidence`, 3-4 `met-with-evidence`

**Reading a page** 5 `met-with-evidence`, 6 `met-with-evidence`, 7 `not-started` - one
question needing search *and* fetch has not been run

**Independent** 8 `met-with-evidence`, 9 `met-with-evidence`, 10 `met-with-evidence`

**Sources** 11 `blocked`, 12 `blocked` - both on the same finding, both answered by cycle 5's
structural fix

**Visibility** 13-15 `met-with-evidence`
**Boundaries** 16-18 `met-with-evidence`
**Failure and recovery** 19-24 `met-with-evidence`
**State** 25-26 `met-with-evidence`
**Configuration** 27-29 `met-with-evidence`
**Exit** 30 `met-with-evidence`

## Goal check

**Not met.** 27 of 30 carry evidence, from 24. Two moved to `blocked` - honestly, with the
route out named.

## What is left

- **AC 11, 12** - the sources line. Cycle 5.
- **AC 7** - one question needing both a search and a fetch. One live run.

Three searches were spent this cycle. Throttling did not occur.

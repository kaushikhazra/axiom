# Cycle 5 - 2026-08-25 09:22 IST

The sources line, and AC 7 live. **179 tests green, from 172.** `src/` 1189 -> 1246.
**All 30 criteria met.**

## Axiom names its own sources

Cycle 4 proved no wording gets a 7B model to cite addresses that are both present and real -
it omits, invents, or retreats. So axiom says it instead, from what was actually retrieved.

**Two lists, kept apart, because they are different claims:**

- `axiom: read:` - pages actually fetched, successfully.
- `axiom: found, not read:` - addresses a search returned.

Collapsing them would have been the same false claim the model was making, told by axiom
instead. A snippet is not a page.

Both carry the `VOICE` prefix, so a reader can tell axiom's lines from the model's sentences.
That matters because of the limit below.

### How it knows

The loop already has the call, its arguments and its result. A fetch that did not begin with
`error:` retrieved a page; a search's result is parsed by `tools.addresses_in`, which lives
next to the format it reads - one bare address on its own line, so an address mentioned inside
a snippet is not mistaken for a result. A test covers exactly that.

`fetch_page`'s "no readable text" now carries the `error:` prefix like every other failure,
so the loop needs one rule rather than a list of special cases.

Per turn, never cumulative. A later answer inheriting an earlier question's sources would be
the same false claim one turn removed, and a test pins it.

## AC 7, live, and the sources line with it

```
$ Find the official Python documentation page for pathlib, then read it and
  tell me in one sentence what PurePath is for.

> axiom: search_web(query=...)
  | ...
> axiom: fetch_page(url=https://docs.python.org/3/library/pathlib.html)
  | ...
From the official Python documentation, PurePath is a class that represents
filesystem paths in a way that is independent of the underlying operating
system...
axiom: read: https://docs.python.org/3/library/pathlib.html
axiom: found, not read: https://pathlib.readthedocs.io/,
  https://docs.python.org/3/library/filesys.html,
  https://www.w3schools.com/python/ref_module_pathlib.asp,
  https://www.geeksforgeeks.org/python/pathlib-module-in-python/
```

Search, then read, then answer - one flow, no prompting between: **AC 7**.

One page listed as read, and it is the one that was fetched. Four others correctly separated
as found. **AC 11 and AC 12**, from data rather than from the model's word.

The model's own prose says "From the official Python documentation" and invents no address at
all - which is what the strictest description bought, and why it was kept.

## The limit, recorded rather than hidden

**Axiom cannot stop the model writing an invented address in its prose.** Nothing in this
loop makes a model honest.

What the sources line gives the user is something true to check *instead* - and the `VOICE`
prefix is what makes that distinction visible on screen. AC 12 is met because axiom does not
present unread addresses as sources; it is not met in the sense of guaranteeing every URL in
the model's sentences is real, and this log should not be read as claiming that.

## The transcript

Purely additive, two lines:

```
185a186  > axiom: found, not read: https://example.invalid/teal
207a209  > axiom: read: https://example.invalid/page
```

Worth noting what did **not** change: the throttled-search and unreachable-address scenarios
gained nothing, because neither retrieved anything. AC 12 is visible in the transcript itself.

## Criteria status

All 30 `met-with-evidence`.

**Startup** 1 · **Searching** 2-4 · **Reading a page** 5-7 · **Independent** 8-10 ·
**Sources** 11-12 · **Visibility** 13-15 · **Boundaries** 16-18 ·
**Failure and recovery** 19-24 · **State** 25-26 · **Configuration** 27-29 · **Exit** 30

The four that closed this cycle: **7** live, **11** and **12** by the sources line, and
**24** measured in cycle 4.

## Goal check

**Met.** All 30 carry evidence, the network-facing ones from real runs, and the suite is green
and hermetic - 179 tests with the host on a dead port and all three axiom variables set
hostile.

Following `loop.md` exit 1: merge, then hand over to #32, the last in the queue.

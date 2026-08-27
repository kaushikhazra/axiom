# Cycle 3 — the four gaps, closed

**Commits** `feat(#60): a switch, NO_COLOR, and the one construct worth holding`,
`fix(#60): a table's own blank lines, and three criteria measured not argued`
**Suite** 567 → **593**, green with no Ollama running. **Golden transcript unchanged.**
**Breaks** 8 → **18**, no survivors.

---

## Tables

The one construct held back, and that is a rule rather than a habit: AC 8 forbids holding
a fence's contents and AC 10 forbids holding anything else.

Column widths are not known until the last row has arrived, so a row drawn alone is only
its own text. Rows are held; when a line arrives that is not a row — or the reply ends —
the whole table is drawn at once.

**Holding costs nothing that was ever committed.** A held row is echoed as it is typed and
then taken back with `\r` + erase, so the next row is typed over it, and the finished
table is written below. Nothing that reached the scrollback is touched, so AC 7 still
holds exactly and there is still **no cursor-up anywhere**.

### The decision: rows are typed and taken back, not held silently

Recorded because the alternative is defensible. Not echoing a held row at all would avoid
the churn on that one line, but it would mean the user sees *nothing* while a table
arrives — and the wait is not short:

**Measured against `qwen2.5:7b` on the local Ollama, twice: 4.29s and 4.49s**, on replies
of 14.0s and 11.9s. The hold begins when the first row completes and ends when the last
one does. Two samples, so: this is the order of magnitude, not a distribution.

Four seconds of a blank screen would read as a hang. Four seconds of rows typing
themselves reads as work happening. That is the trade, and it is the reason for the churn.

The wait is bounded by the table's own length and affects nothing else in the reply — the
prose before it streams normally. The alternative to paying it at all is showing the rows
as raw pipes, which is what AC 1 rules out.

### What counts as a row

A line whose **first non-space character is a pipe**. Deliberately tight. Markdown allows
a table without leading pipes, but treating any line *containing* one as a row would
swallow a shell pipeline or a regex alternation into a table that never closes. Missing a
table reads badly; eating a paragraph loses the answer.

A single `| stray |` line is not a table — markdown needs the delimiter row — and Rich
draws it as a paragraph. It is shown, not swallowed.

---

## The switch (AC 25, AC 27)

`--no-render` / `$AXIOM_RENDER`, in the same shape as `--no-tools`, `--no-web` and
`--no-mcp`. Off takes **the same path a redirected run takes**, so "off" is the behaviour
the golden transcript already records and there is one plain path rather than two that
have to be kept identical.

**A decision, recorded:** rendering is *not* tied to `--no-tools`. Tools, the web and MCP
are things the model may *do*, and `--no-tools` reasonably takes all three. Rendering is
about reading the answer, and someone who wants a session without tools has said nothing
about how they want to read it.

**A limitation, recorded:** with `AXIOM_RENDER=off` in the environment, no flag turns
rendering back *on*. That is true of `--no-tools`, `--no-web` and `--no-mcp` too — it is
what `store_true` with an environment default means. Inventing a `--render` for this one
setting would make it the odd one out. If it should change it should change for all four
at once, which is a decision about `config.py` rather than about #60.

---

## NO_COLOR (AC 26)

**Colour goes; formatting stays.** A heading is still bold and underlined; inline code
loses its cyan. That is the convention's own wording, and it is what Rich already does
natively — measured before deciding, in `.tmp/nocolor.py`:

```
NO_COLOR unset :  '\x1b[1;36;40minline code\x1b[0m'
NO_COLOR set   :  '\x1b[1minline code\x1b[0m'
```

So Rich needed nothing. What needed doing was the **cyan this module writes itself** for
fenced code — hand-written, so nothing was honouring anything on its behalf. The dim on a
fence marker is an attribute rather than a colour and stays.

**A decision, recorded:** *presence*, not non-empty. The published convention says "set to
a non-empty string"; Rich tests for `"NO_COLOR" in environ`. Rich draws most of what
reaches the screen here, so agreeing with the renderer beats agreeing with the
specification and then disagreeing with itself — a session where headings lose their
colour and fenced code keeps it is the worse outcome of the two. A test pins it.

---

## Scrolling, wrapping, resize (AC 11, AC 12, AC 13)

Cycle 2 called these "an argument, not a measurement", correctly. Now measured as
properties rather than by simulating a terminal:

- **AC 11** — a 200-line reply emits 200 lines, no ellipsis, no truncation. This is
  precisely what `rich.Live` would have failed.
- **AC 12** — no line padded out to the console width, at 40, 80 and 200 columns.
- **AC 13** — the width is changed **seven times mid-reply** (80, 80, 40, 200, 30, 120,
  60). Five lines in, five lines out, no cursor-up, the last line intact. A resize corrupts
  a stream that redraws; nothing here is redrawn.

---

## Three more that were argued rather than measured

Cycle 2 marked AC 16, AC 20 and AC 24 met on the strength of *where the code sits*. That
is the shape of finding this loop has caught eleven times, so they were measured with
rendering on:

- **AC 16** — history holds the reply as written, markup intact, and no escape sequence
  appears anywhere in what goes back to the model.
- **AC 20** — a reply that turns out to be a tool call never reaches the renderer. The
  announcement text appears nowhere on screen, `read_file(path=x)` is called, and the
  answer after it arrives.
- **AC 24** — a snowman and an emoji survive rendering, so it does not become a second
  place a reply can die.

---

## Break and watch: 18, no survivors

Ten new ones this cycle. **Two of the new tests survived their break first**, and both are
the same shape as cycle 2's three:

- **the pipe test asserted on the byte stream.** A held row is echoed verbatim before it
  is taken back, so the text is in the bytes whether or not it was wrongly held.
- **then it called `finish()` before looking.** A wrongly held line is drawn when the reply
  ends, so it reaches the screen eventually anyway. What a wrongly held line actually costs
  is **AC 10** — it arrives at the end of the reply instead of when it was written — so
  that is what the test now measures: the line must be on screen **while the reply is
  still arriving**.

Two of the breaks were also wrong and had to be fixed before they proved anything: `[] or
X` is `X`, and `re.compile(r"\|").match(...)` is anchored so it never matches a pipe
mid-line. **A break that cannot break anything is as useless as a test that cannot fail**,
and both looked fine while being no-ops.

Config breaks now run too, restored from the harness's **own saved copy** — never from
git, which is what cost cycle 2 the whole renderer.

---

## One real bug, found by reading a real reply

Every table came out with **a blank line either side of it**. Rich draws an empty top and
bottom border row, and they arrive as lines that are empty apart from their escape
sequences — `strip()` does not see them as empty, because an escape sequence is not
whitespace.

No test caught this. The live run did.

---

## A real table, before and after

`qwen2.5:7b`, local Ollama. Note the model's own rows are ragged — `| 1991|` with the
space missing — and the drawn table is square regardless.

```
=== BEFORE ===
| Language | Year | Typing Discipline |
|----------|------|------------------|
| Python   | 1991| Dynamically typed |
| Rust     | 2010| Static            |
| Go       | 2009 | Static           |
| C        | 1972| Static           |

=== AFTER ===
  Language   Year   Typing Discipline
 ─────────────────────────────────────
  Python     1991   Dynamically typed
  Rust       2010   Static
  Go         2009   Static
  C          1972   Static
```

---

## Status of all 29

**Met, with evidence.** 1 (tables included), 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14,
15, 16, 20, 21, 22, 23, 24, 25, 26, 27, 28.

**Met, by the golden transcript being unchanged.** 17, 18, 19, 29.

**All 29 have evidence.** That sentence is exactly the one cycle 2 of eleven previous
issues wrote before a cold read found something, so it is a claim awaiting a hostile
reader rather than a conclusion.

---

## What cycle 4 does

**The cold read**, and it is the whole of the cycle. Read the 29 criteria from GitHub
first — before this log, before the diff — and attack each one rather than confirming it.
The three vacuous tests in cycle 2 and the two in cycle 3 were all found by breaking
things, which means the same class of test is likely still in here somewhere unbroken.

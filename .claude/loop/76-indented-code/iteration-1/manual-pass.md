# #76 — the manual pass

**All thirteen criteria are met by test, each proved by a break.** Nothing here is owed
because it could not be tested. What is here is owed because a test measures what axiom
*emits*, and only a person can say what a terminal *draws*.

Run it as `axiom` in a normal terminal and ask a model something that makes it show an
example — the defect was found that way, not by reading.

## What to look at

| | What to do | What should happen |
|---|---|---|
| 1 | Ask for a code example and hope the model indents rather than fences | The block reads to the end of every line |
| 2 | Narrow the window to about half and ask again | Still every character, wrapped at the block's own indent rather than at column zero |
| 3 | Compare an indented block against a fenced one in the same reply | Both read as blocks; neither is painted |
| 4 | A reply with a nested list in it | Still a list — glyphs, depths, no grey bar |
| 5 | A long block, streaming | It arrives line by line with no flicker and nothing drawn twice |

## The one judgement a test cannot make

**Does an unpainted, indented block still read as a block?**

Cycle 2 decided it does, and the decision was reasoned rather than seen: `_MARKDOWN_STYLES`
already records #77 AC 20's position that a block nobody can lex is *delimited, not coloured*,
because a colour is a claim about the content that nothing supports. A fenced block with no
language gets no paint either — it is set apart by its markers. An indented block has no
markers, so what sets it apart is where it sits.

**If it does not read as a block on a real terminal, that is the finding**, and it is a
criterion (AC 3) rather than a preference. The alternatives, in order of least surprise:

1. leave it, and accept the indent as the delimiter;
2. dim the block, the way fence markers are dimmed;
3. paint it, and revisit #77 AC 20 — which would then need to change for fenced blocks too,
   or the two are inconsistent again.

## Two things measured and deliberately left

- **A whitespace-only line commits a row of its own spaces** — `['', '    ', '']` between the
  lines around it. The erase takes it back before it reaches the screen, so AC 9 holds. It is
  what every whitespace-only line has always produced, indented or not, and is not this
  issue's to change.
- **Wide characters are sliced by character, not by cell.** A CJK code block can spill one
  column and wrap. Every character still arrives, which is AC 2; the rectangle is what
  suffers. No criterion here is about a CJK code block, so it is untested rather than solved.

## Owed alongside this

#72, #73 and #74 are all still waiting on a manual pass, and all three are the same renderer.
Worth doing in one sitting.

---

## What happened — 2026-09-02

**Driven by hand by Kaushik. Everything satisfies.** This one sitting covers **#76, #72 and
#73**: they are the same renderer, and the build was `feature/76-indented-code`, which sits
directly on the master already carrying #72, #73 and #77. 892 tests green in 82s beforehand.

One reply carried all four shapes at once - an indented block, a fenced block beside it, a
three-level nested list, and an over-wide quote - then the same prompt at half the window
width, then again under `--no-render` for comparison.

| | Verdict |
|---|---|
| Indented block reaches the end of every line, at full and half width | pass |
| Wraps at the block's own indent rather than column zero | pass |
| Indented and fenced blocks both read as blocks, neither painted | pass |
| Nesting: three levels, three indents, shallower returns to its own level | pass |
| Wide quote wraps with its marker carried onto continuation lines | pass |
| Streaming draws once - no flicker, nothing redrawn shorter | pass |
| Words and their order identical against `--no-render` | pass |

**The judgement is answered: an unpainted indented block does read as a block.** Cycle 2
reasoned it would, from #77 AC 20's position that a block nobody can lex is delimited rather
than coloured. Seen on a real terminal, the indent is enough. #76 AC 3 holds as built, and
neither of the alternatives - dimming it, or painting it and reopening #77 AC 20 for fenced
blocks too - is needed.

**The two measured-and-left items stand unchanged.** The whitespace-only line is erased before
it reaches the screen, and wide characters are still sliced by character rather than by cell -
a CJK block can spill a column. No criterion covers it; it remains untested rather than solved.

**#74 is still owed a pass.** It is the scheduler, not the renderer, so it was not part of this
sitting.

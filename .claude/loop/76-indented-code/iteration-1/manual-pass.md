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

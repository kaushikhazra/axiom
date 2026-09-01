# Assumptions

## The design is settled. This loop implements it and does not redesign it.

It was agreed interactively on 2026-09-01 and is written at
`C:/Projects/axiom/.tmp/chooser-look-decision.md`, with runnable mock-ups beside it:

    .tmp/mock_chooser.py       the model list, four layouts, --gold for the palette
    .tmp/mock_startup.py       the flow: chooser, clear, info panel. --static for all states
    .tmp/mock_reply.py         the reply's palette, through the real renderer
    .tmp/mock_fallback.py      the unlexed fence, four candidates, each checked against AC 3
    .tmp/mock_turn.py          one-line tool calls, and the two greys
    .tmp/mock_quiet_turn.py    what replaces them, drawn live

**A cycle that wants to change the design stops and asks.** It does not decide.

## The palette

    accent   #daa900   Mountain Leverage's --uicore-secondary-color, off their theme
    voice    #70747e   their --uicore-body-color, rgba(16,24,40,.6) resolved over white

`#70747e` is **derived, not published** — Mountain Leverage names no grey. It was chosen
over the lighter `#a3abb0` because axiom does not know whether it is on a light or a dark
background, and the mid grey survives both.

The accent goes on: panel borders, panel titles, row numbers, the marked model, every
structural mark in a reply, and the prompt. The voice grey goes on everything axiom says
about itself. **The model's answer and the tool's name keep the terminal's own
foreground** — the answer is meant to be the brightest thing on screen.

## Settled decisions that a cycle will be tempted to re-open

- **Aligned columns**, not ragged. It costs 11 rewritten assertions and that price is
  accepted.
- **The panel title carries `models on <host>` whole**, rather than splitting it into title
  and subtitle. This keeps 10 assertions passing and reads better.
- **The unlexed fence gets no styling at all.** Kaushik's rule: if we do not know the
  language, we do not know how to colour it. The dim fence markers are what delimit it.
  **AC 20 is a reinterpretation of #60 AC 3 and must be written down as one** — in a cycle
  log and in the commit — not absorbed by quietly editing a test.
- **Fenced code with a known language keeps its syntax highlighting.** A language needs
  more than one hue.
- **Tool calls: variant D.** One grey line after the turn — `·  4 tools, 2 failed`. No
  per-call lines, no per-failure lines.
- **No scaffolding.** Nothing temporary goes in now to be removed when the log lands. The
  per-call detail goes to a log as a separate piece of work, later, not in this issue.
- **`console.clear(home=True)`** — clears the screen, leaves scrollback intact.
- **The prompt glyph is `>`**, in the accent colour.

## Constraints from the repository

- **Branch `feature/77-look`.** A cycle that wakes on `master` switches; it does not commit.
- `uv run pytest` must stay green and hermetic. The live lane stays deselected by default.
- **No compound shell commands.** One command per invocation, in Bash and in PowerShell —
  `~/.claude/CLAUDE.md` earns this rule with a deleted repository.
- Rich is already a dependency. Reach for it rather than hand-rolling; `terminal.py` already
  builds Consoles with `legacy_windows=False`, and dropping that flag silently throws away a
  link's address.
- **Assume a fresh context.** Only these files exist. Read the issue from GitHub before the
  diff and before the previous log.

## A known gap in the instrument

`tests/screen.py` strips SGR and CSI but **not OSC-8 hyperlinks**, so two identical renders
of a reply containing a link compare unequal. It did not affect #72 or #73 — no links in
those cases — and it will affect AC 34. Normalise the link id, or fix the screen model and
say so.

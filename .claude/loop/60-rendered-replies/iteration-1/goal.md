# Goal

Let a user read a reply as formatted text while it is still arriving - meeting every one of the
29 acceptance criteria on GitHub issue #60.

Kaushik asked for this after reading back a real session: *"the markdown should render a little
better, and the interface should look like at least Claude Code."* Every model on this machine
emits markdown, and a terminal shows it literally - `**bold**`, backticked fences, `-` bullets -
so a long answer full of headings and code is something to decode rather than read.

The research was done 2026-08-27 and the stack is settled: **Rich, inline.** The input line -
`prompt_toolkit`, history, multiline - is a **separate story that has not been written**, and is
not this row's business.

**The hard part is not markdown. It is streaming markdown.** A fenced block cannot be rendered
until it closes, and mid-stream ` ```python ` is an unterminated block. The naive approach -
`rich.Live` re-rendering the whole reply on every chunk - produces a scrolling smear on any reply
longer than the window, which is why **AC 7 is written as "a line that has been shown does not
move again"**. That criterion is what separates a good implementation from an obvious one.

Done when: all 29 criteria of #60 are met, each with evidence recorded in a cycle log; the suite
is green and hermetic; the piped path is byte-identical to today; and the golden transcript's
change is accounted for line by line.

# Action

**Implement the renderer at the `terminal.py` seam.** Cycle 1 settled the approach with evidence:
commit finished lines with an ordinary `print`, re-render only the unfinished tail, and never let
Rich own the cursor.

## 1. Check the ground

- Full suite. **539 is the floor.**
- `diff .tmp/transcript-baseline-60.txt tests/baseline/transcript.txt` - **unchanged**, and it
  must stay that way. If it moves, stop and find out why before doing anything else.

## 2. The renderer

A small object in `terminal.py` holding the reply so far, with two operations:

- **feed(text)** - accumulate, decide which lines are now *final*, print those, and re-render the
  tail.
- **finish()** - flush whatever remains, close any construct that never closed.

**What makes a line final** is the whole design. A line is final when nothing that arrives later
can change how it renders. Inside an unclosed fence, a line's *content* is fixed even though the
block is not - so it can be shown as code as soon as the fence opener is complete. Outside a
fence, a line is final once a newline follows it and it is not a setext heading candidate.

**Do not let Rich move the cursor.** Use `Console.render_lines` or `Console(file=...)` capture to
turn markdown into styled lines, then print them. `Live` is not used.

**Plain when not a terminal** - checked before any of this, and returning the old path exactly.

## 3. Wire it in

`show_piece` is called with `reply[shown:]` - the new text only - and `end_reply` ends the reply.
Those two are the seam. **Nothing above `terminal.py` should need to change**; if it does, say
why in the log.

AC 20: `_could_still_be_a_call` still decides whether anything is shown. The renderer only ever
sees what the loop releases, and a reply that turns out to be a call is never fed to it.

## 4. The measurements, not impressions

- **AC 7** - capture the byte stream for a reply taller than the screen. Assert **no line is
  emitted twice** and **no cursor-up crosses the committed region**.
- **AC 5** - for a set of replies, every non-markup character sent appears in the stripped
  output. Property-style, several inputs.
- **AC 9** - a half-arrived `##` is not styled as a heading; a fence opener split across chunks
  does not produce a code block until it is complete. Feed text **four characters at a time**,
  because that is what a real stream delivers.
- **AC 14, AC 15** - piped output byte-identical to the saved baseline.
- **AC 16** - the payload sent to the model is unchanged by rendering.
- **AC 28** - force the renderer to raise; the reply still appears in full as plain text.
- **AC 21** - an empty reply prints nothing and leaves #58's spacing alone.

## 5. The judgement, recorded not asserted

Run a real reply through it against the local Ollama and **paste the before and after into the
log**. Kaushik asked for this because a transcript read badly; the log has to show that it reads
better. One sample is enough to *show* it and not enough to *claim* it - say which.

## 6. Then

Full suite, hermeticity command, transcript. Break the renderer and record what goes red, naming
survivors. Write cycle 3's action: the cold read.

## Record

Status for all 29. What makes a line final, and why. The AC 7 capture. The before and after.
Whether anything above `terminal.py` changed.

**Write no questions into anything.** Decide, record the decision and the reasoning, carry on.

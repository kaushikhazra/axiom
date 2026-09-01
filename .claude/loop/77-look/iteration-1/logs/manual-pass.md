# The manual pass over #77

2026-09-01, after the loop converged. **Not a cycle** - the loop had already ended
and its cron was deleted. This is the thing the loop could not do for itself: a
person at a real terminal, looking.

## Why it could not have been done by the loop

The panel, the accent, the prompt and the tool summary are drawn **only at a
terminal**. Every automated run in this repo captures a `StringIO`, so the whole
of #77's visible behaviour is on a path that no test process can enter. 876 tests
say the behaviour holds; until this pass, nobody had seen any of it.

## What it found

**One defect, and it was invisible to the suite.** Kaushik ran a turn and pasted:

    > list the folder

    I am currently working in ... I do not have a tool available to list the
    contents of the directory directly.

      ·  1 tool

    >

Two things wrong with that line, neither of which a test asking "is the summary
present?" could see:

- it sits **below the answer**, so you learn what the answer rested on after you
  have read it
- it sits between two blank lines just above the prompt, so it reads as belonging
  to the **next** turn rather than the one it describes

Fixed: the summary is drawn on the first fragment of reply that follows any tool
call, with `end_turn` keeping a copy for the turn that never produces another word
and a flag stopping the two callers saying it twice. Three tests, three breaks,
all red. 873 to 876.

**A wrong diagnosis of mine, corrected before it reached an issue.** I claimed
`run_command` had swallowed a shell error and the model had answered from it.
Measured: `run_command('ls')` works, and the folder held only `.axiom` - a
dotfile - so `ls` genuinely returned nothing and "there are no files or folders"
was a fair reading. The lesson is the ordinary one: the reproduction took one
command and the guess took three paragraphs.

**A real defect, filed as its own story.** In the same session the model said *"I
do not have a tool available to list the contents"* while a tool had just run
successfully. That is [#78](https://github.com/kaushikhazra/axiom/issues/78).

**Third sighting of that pattern in this repo, and worth stating plainly: the
per-call display is what caught the first two.** #77's variant D is quieter and it
is also the reason nothing on screen resolved the contradiction. That tension is
now #78's to settle, not #77's.

## The verdict

Kaushik, after re-running the pass: **everything looks good.**

Checked at a real terminal: the chooser's border and aligned columns, the clear
and the panel with scrollback intact, a tool turn with the summary above the
answer and nothing per call remaining, a turn with no tools showing no line, the
reply's gold on headings, lists and table rules, an unlexed fence carrying no
colour, wide lines and nested lists at a narrow window, and `NO_COLOR`.

## Still owed

- **#72, #73 and #74 have never had this treatment.** The pass was paused for #77
  and is still owed. `.tmp/testing-72-73-findings.md` holds what was found before
  it stopped; #74 was never started, and the screen model does not reach it
  because scheduling is about elapsed time.
- **Nothing is merged.** `feature/77-look` is ahead of `master`.

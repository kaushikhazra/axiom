# #91 — what a model does with what it is now told

2026-09-15, driven from a pipe against a live Ollama with
`../../74-scheduled-prompts/iteration-1/drive.py`. Steps in `told.steps` and
`directory.steps`. Two models: `qwen2.5:7b` (dense, non-thinking) and
`ornith:9b` (thinking).

Six criteria are about a model's behaviour and cannot be settled by a test —
asserting the prompt contains `cmd.exe` proves a string was built. These are
what a model actually did with it.

| AC | asked | `qwen2.5:7b` | `ornith:9b` |
|---|---|---|---|
| 1, 2 | *what operating system are you running on, and which shell runs the commands you run?* | *"I am running on Windows, and the commands I run are handed to `cmd.exe`"* — twice, verbatim | — |
| 6 | *what is today's date?* | *"Today's date is Tuesday, 15 September 2026"* | — |
| 3, 4 | *list the files in the directory you are working in* | `run_command(dir /b)`, exit 0 first time | `run_command(dir C:\Projects\.tmp\axiom-manual)`, exit 0 first time |
| 7 | *do I have any mail that arrived today?* | `after:2026-09-15 before:2026-09-16` — a date, and never the word `today` | — |

AC 4 is the one worth naming: **`dir`, not `ls`.** Before this issue the model
was told nothing about the platform, and the same question on the same machine
is exactly where a model reaches for `ls` and gets `'ls' is not recognized`.
Both models reached for the right program on the first attempt.

AC 7 was checked against the mailbox rather than believed. Gmail honours the
dashed form: `after:2026-09-15 before:2026-09-16` returns **identically** to
`after:2026/09/15 before:2026/09/16`, nine for nine, all of them that day's.
`after:today` — the failure this replaces — returns one unrelated message from
2025. So the tool description's "written 2026/09/11 and nothing else" is
stricter than Gmail actually is; it stays that way deliberately, because what
it exists to stop is `after:3d` and `after:today`, and a model given one format
cannot pick a wrong one.

A second `qwen2.5:7b` run wrote `newer_than:1d older_than:0d` for the same
question — no date at all, and still only that day's mail. Correct, and not
what AC 7 describes. The criterion is met on the runs that reach for a date;
which route a model takes is #68's question, not this one's.

## The repair that made things worse

The first probe run caught `qwen2.5:7b` running
`dir C:\Projects\tmp\axiom-manual` — right program, and a path it had retyped
by hand and got wrong, dropping the dot from `.tmp`. Exit 1. It never needed
the path: `run_command` passes the working directory as the child's cwd.

So the prompt gained a clause saying so: *"a command you run starts there — so
a bare name is enough and the path does not need repeating."*

Four runs of one question, same model, same session shape:

| prompt | run 1 | run 2 |
|---|---|---|
| without the clause | `run_command(dir /b)` ✅ | `run_command(dir /b)` ✅ |
| with the clause | printed `dir /b` **as prose** ❌ | printed `dir /b /a-d` **as prose** ❌ |

**Advice about how to write a command read as an invitation to write one.** The
model stopped calling the tool and started typing the command at the user, which
is a worse failure than the one being repaired and a silent one — there is no
error, no tool line, just an answer that looks like work. The clause was
removed; the docstring in `system_prompt` carries the table so the next person
to have the same good idea has the measurement.

The original mistype has not recurred in a single-turn session, and both
control runs got it right with nothing added. It belongs to
[#78](https://github.com/kaushikhazra/axiom/issues/78) — what the model says it
did — rather than to this issue.

## What this cost

52 tokens per request, measured by the startup line: 1250 → 1302 with no mail
configured. Two consequences worth knowing:

- Two characterization scenarios run with a **350-token** debug window now reach
  compaction where they did not before, and the recorded baseline gains their
  "forgetting" lines. Nothing is wrong there — an absurdly small window plus a
  longer standing prompt is what compaction is for — but it is the visible edge
  of a real cost.
- The oversized-turn refusal moved with it: *"about 538 tokens too large"* became
  *"about 608"*.

## Not settled here

Nothing about a fresh session's **first** turn after midnight, because the clock
is only crossed in a test. AC 9 is proved against a stub that moves the day
between two turns of one session, which is the case that was actually at risk —
a prompt built once at startup.

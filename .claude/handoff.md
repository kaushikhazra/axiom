# Handoff — skills shipped, four stories waiting on a testing pass

Rewritten 2026-08-31 at the end of the session that built #75. The previous version pointed
at formal testing of #72, #73 and #74; **that has not happened.** What changed is that all
four stories are now merged and pushed, so the testing pass covers one build instead of
three.

**The next session picks up here: formal testing, then two decisions.**

## Where things stand

`master` is **836 tests plus one deselected**, everything pushed, no open PR, nothing
scheduled. `origin/master` is level with local.

| issue | what it is | state |
|---|---|---|
| [#75](https://github.com/kaushikhazra/axiom/issues/75) skills | 44/44 criteria, break-proven | **closed**, merged |
| [#74](https://github.com/kaushikhazra/axiom/issues/74) scheduled prompts | 33/33, converged | open, merged, untested formally |
| [#73](https://github.com/kaushikhazra/axiom/issues/73) nested lists | 13/13, converged | open, merged, untested formally |
| [#72](https://github.com/kaushikhazra/axiom/issues/72) wide lines | 21/21, loop stopped unconverged | open, merged, untested formally |
| [#68](https://github.com/kaushikhazra/axiom/issues/68) summary across models | not started | open |

The three open merged ones stay open **because their code shipping is not the same as their
behaviour being checked by a person.** Do not close them on the strength of a green suite.

## Start here

```
cd C:\Projects\.tmp\axiom-manual
uv run --project C:/Projects/axiom axiom
```

**`--project`, not `--directory`.** `--directory` moves the working directory into the repo,
which CLAUDE.md's tool-testing rule forbids, and then needs `--working-directory` to undo.

Startup now says **`11 tools including web`** and **`about 1250 tokens`** with no skills
configured. `--no-web` gives 9 tools and 1018.

## Three decisions waiting

**1. The indented-code defect.** A line indented four spaces that is *not* a list item still
crops - 41 characters lost at width 40. It belongs to neither #72 nor #73, and #73 converged
after being handed it. A drafted issue with 13 criteria and the measurement is at
`.tmp/issue-indented-code.md` (gitignored, still on disk). A one-line change takes the loss
to zero and renders a three-line block as three blocks over eleven rows, because an indented
code block has **no closing delimiter**. Fixing it properly needs the held-lines exemption
that only tables have. **New story, or scope on #72?**

**2. What every request now costs.** 807 tokens before #74, 1111 after it, 1250 after #75 -
**55% up on two stories**, before a single skill or scheduled job exists. #75 gave 257 back
by declaring only the skill tools an empty catalogue can use, and the residual 139 is
`write_skill`, which cannot be dropped without making the feature unreachable from a fresh
project. `--no-skills` and `--no-mcp` take it to zero for a user who wants that. **Worth
revisiting whether the scheduler's three tools earn their 304.**

**3. One thing in `master` that was never measured end to end.** `call_from_text` now
translates a skill named where a tool belongs into `invoke_skill` - Kaushik's call, made
after the loop converged. It rests on a census showing five of qwen2.5-coder's ten attempts
arrive in that shape and were being dropped. **The confirming live run was not taken**, so
"worsens no model" is a structural argument, not numbers. Six minutes closes it:

```
uv run pytest -m live -q -s
```

Recorded in `.claude/loop/75-skills/iteration-1/logs/after-convergence.md`.

## What skills are, in one paragraph

A skill is a folder under `.axiom/skills/` holding a `SKILL.md`: markdown instructions
behind frontmatter carrying a name and a description. Only the name and description ride on
a request; the instructions are read from disk at the moment of invocation, so editing one
mid-session takes effect without a restart. `/skills` lists them, `/skill <name> [text]` runs
one, and the model gets four tools - read, write, delete, invoke. A `SKILL.md` written for
another agent loads unchanged; fields axiom does not use are ignored.

## What the live lane is

`tests/test_skills_live.py`, marked `live` and **deselected by default** through
`pyproject.toml`. It needs Ollama and takes six minutes. `uv run pytest` never runs it, which
is what keeps the wall-clock readings in the loop logs meaningful.

Per-model counts from it, ten runs each: gemma4 10/10, ornith 10/10, qwen2.5 10/10, qwen3.5
9/10, qwen2.5-coder 2/10, gemma2 no tool support. **The noise floor is plus or minus one** -
two runs of the same measurement with no code change moved two models by one each.

## What #75's loop learned that a reader should know

Eleven cycles' worth, all earned:

> **A break big enough to be easy to write takes several tests with it and proves nothing
> about the one it was aimed at.** Three separate cycles lost a criterion this way and had
> to re-run a narrow break to earn it. A test that goes red for the wrong reason has not
> been proven.

> **A score below the pack is a question about the measurement before it is an answer about
> the model.** qwen2.5-coder scored 0/10, then 2/10. The first was the instrument counting
> only structured calls; the second was axiom failing to route a correct intention. Neither
> was the model, and both looked exactly like it. **0/10 is why it got caught** - at 3/10 it
> would have read as a plausibly weak model and stood.

> **A scripted break that reports nothing did not run.** Twice: once printing no summary
> line at all, once `NO MATCH`. Both would have been read as "no test noticed", which is the
> opposite of true. Anything with a backslash escape goes through the Edit tool.

> **Grep the criteria numbers out of the tests and diff against the issue.** One command. It
> caught two criteria that were genuinely asserted but cited nowhere - covered by accident
> rather than on purpose, which is one step from believed-covered and not.

> **"Already true, just needs a test" is a claim to check, not to act on.** AC 14 was that
> and held. AC 34 was assumed the same way and was false - invoking a skill twice duplicated
> its instructions.

> **Read the baseline diff rather than accepting it.** Regenerating it once produced a
> correct-but-noisy line; narrowing the code let the baseline be *restored* instead of
> updated, leaving observable behaviour byte-identical.

## Loop records

`.claude/loop/72-wide-lines/`, `73-nested-lists/`, `74-scheduled-prompts/`, `75-skills/` -
each with `goal.md`, `observe.md`, `assumption.md` and a `logs/cycle-N.md` per cycle. #72 ran
5 cycles, #73 3, #74 7, #75 11.

**Note on timestamps:** several early logs in #72, #73 and #74 carry times from an assumed
clock, running up to an hour ahead. #75's are read. Nothing was decided by a timestamp.

**Nothing is scheduled.** Every cron was deleted as its loop ended.

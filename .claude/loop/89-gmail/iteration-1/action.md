# Action

Cycle 4's constraint: **`forget()` and `status()` exist and no user can reach them.** AC 15,
AC 16 and AC 22 are about the user doing something, and there is no `/mail`.

**Build the command. Then do the AC 29 sweep** — it is reading, not writing, and leaving it
to the end is how it gets claimed rather than done.

## Before writing anything

`gh issue view 89`. Two claims have already been made against #90's numbering.

**Commit before breaking.** Cycle 3 lost eight edits; cycle 4 committed first and lost
nothing.

## The command

`__init__.py:748` onward is a flat if-chain on a single-line `command`, one branch each.
Follow it exactly — this is a new surface, not a new pattern.

- `/mail` alone — what axiom holds: the account, when it was granted, or that there is
  none (AC 22). `Mailbox.status()` already returns this and carries no secret.
- `/mail forget` — revoke (AC 15). The next request asks again (AC 16), which
  `forget()` already guarantees by clearing both the cache and `_service`.

**Match the `/skills` before `/skill` ordering rule**, and read the comment that explains
it: `/skills` is tested by equality *before* `/skill` is tested as a prefix, or `/skills`
is read as `/skill` with an argument of `s`. The same trap is one letter away here.

**A run with nothing configured must still answer `/mail`.** Say there are no credentials
rather than nothing at all — a user who typed it is owed a reason. This is not AC 1's
concern: AC 1 is about startup, and a command the user typed is not startup.

The drawing goes in `terminal.py` beside `show_skills`, not in `mail.py`. `mail.py` has no
import from `terminal` except inside `mail_announcer`, and that is worth keeping.

## Then the sweep — AC 29 and AC 30

Cycle 1 narrowed this correctly and it has not been done. A token cannot be a tool argument,
so `note_tool` is safe by construction. **The error paths are not.** Read, and write down
what each can carry:

| | |
|---|---|
| `run()`'s `except Exception` | returns `error: {failed}` — what does a `RefreshError` stringify to? |
| `googleapiclient.errors.HttpError.__str__` | includes the request URI. **Check whether an access token can appear in it.** |
| `mail._why` | already tested against a leaky `oauthlib` string; confirm it is the only path a flow failure takes |
| `Mailbox.problem` | names variables, never values — confirm |

The output is a list in `logs/cycle-5.md` of every path checked and what it carries. **If
one can leak, fix it and add a test.** If none can, say what was read — a sweep is only
evidence if it names what it swept.

## Do not claim

- **AC 12** — unreachable while the app is in Testing.
- **AC 4 to AC 10** — the flow needs a real browser. They are owed to the manual pass.
- **AC 3, AC 11** — need a real cached grant.

## What proves the cycle moved

`/mail` and `/mail forget` work in a real run, tested through the same path a user takes.
The sweep is written down with each path named. Full suite green, measured on a full run.

First thing to tackle: **`/mail` in the command chain**, because the sweep is reading and
can follow.

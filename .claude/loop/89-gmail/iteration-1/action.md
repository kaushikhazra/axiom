# Action

Cycle 5's constraint: **fifteen rows left and most need a browser.** This cycle takes the
last ones that do not, then states plainly what is owed to Kaushik's account — because a
loop that starts guessing at rows it cannot drive is a loop that reports itself finished.

## Before writing anything

`gh issue view 89`. Commit before breaking.

## 1. AC 39 — nothing left behind

*"Leaving axiom holds no browser window open and leaves no listener behind."*

`run_local_server` starts a socket. **Assuming the library closes it is the assumption
#43 AC 26 and AC 27 exist to disprove** — and that pair is in this repo because a server
outlived axiom once already.

Read `google_auth_oauthlib/flow.py` around `run_local_server` and establish, from the
code, whether the WSGI server is shut down on every path out — including the timeout path
that raises `WSGITimeoutError`, which is the one a hurried reading would miss. If it is
not, close it. Either way the log says which, and names what was read.

There is a second half nothing has touched: **a `Mailbox` holding a built service when
axiom exits.** `main`'s `finally` stops the servers; it does not know about mail. Decide
whether it needs to, and say why.

## 2. AC 36 — `--no-tools`

*"`--no-tools` prevents the Gmail tools being offered and prevents any browser opening."*

The first half is free — `_prepare` returns `declarations = None`. **Test it anyway**, with
credentials set, because "free" is what cycle 2 assumed about AC 1 before the baseline
caught it.

The second half is the real row: with no tools declared, nothing can call a mail tool, so
nothing can reach the flow. Prove it, do not reason it.

## 3. AC 25 — a message id that does not exist

*"A request for a message that does not exist is reported as such, and the session carries
on."* Gmail answers a bad id with a 404, so this is `failed_call` with a status — check it
reads as *not found* rather than as a generic refusal, and fix it if not.

## 4. AC 40 — exit status

*"A run that only ever failed to get permission still exits 0 by every ordinary route."*
A refusal returns an `error:` string; nothing raises. Test `/exit` and end-of-input after a
refused call.

## Then: write the manual pass, and stop guessing

Everything remaining — **AC 3 to AC 13, AC 21, AC 34** — needs a real Google account and a
real browser. Do not claim any of them.

Write `manual-pass.md` in this folder: one row per owed criterion, what to type, what to
look for. Follow `.claude/loop/74-scheduled-prompts/iteration-1/manual-pass.md`, which is
the worked example in this repo.

**State the prerequisites at the top**, because they are Kaushik's and not the loop's:

- a GCP project with the Gmail API enabled
- an OAuth client of type **Desktop app** — the type that permits a loopback redirect
- `AXIOM_GOOGLE_CLIENT_ID` and `AXIOM_GOOGLE_CLIENT_SECRET` in the environment
- himself added as a test user on the consent screen

And the one that will otherwise be reported as a defect on day 8: **an app in Testing
expires every refresh token after seven days.** That makes AC 12 unprovable past a week and
AC 13 easy to reach. Say which is which in the pass, not afterwards.

## What proves the cycle moved

AC 25, AC 36, AC 39, AC 40 backed by tests. `manual-pass.md` written, with every owed row
named and the prerequisites at the top. Full suite green, measured on a full run.

If those four land, **the loop has taken this as far as it can without Kaushik**, and the
next cycle's honest move is to say so and stop rather than to keep finding work.

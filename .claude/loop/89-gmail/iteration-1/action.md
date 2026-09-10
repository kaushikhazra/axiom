# Action

Cycle 1 found the constraint: **`run()`'s injection chain is exclusive**, so a Gmail tool
gets one dependency and it is not `limits`. Every other criterion is downstream of where
the authenticated client lives and how it reaches a tool. Settle that, in code, this cycle.

**Do not write four tools.** Write the shape and prove it with one.

## First: the branch

`git checkout -b feature/89-gmail`. Master is hook-protected and this is the first cycle
that writes. Commit before anything is broken on purpose later.

## Then, in order

1. **The three dependencies** into `pyproject.toml`: `google-api-python-client`,
   `google-auth-oauthlib`, `google-auth-httplib2`. Run `uv sync`. Record what the
   dependency count and install size actually became — #75 measured its token cost and
   this loop measures wall clock, so an unmeasured dependency is out of character here.

2. **`src/axiom/mail.py`, holding one class.** Session-scoped, mutable, injected — the
   same category as `schedule.Schedule` and `skills.Library`, and it should read like them.
   It owns: the client id and secret, the cached token, whether permission is currently
   held, and the built Gmail service. **It does not run the browser flow on construction**
   — AC 3 says a run with good stored permission opens no browser, and AC 4 says the
   *first request that needs Gmail* opens one. So the flow is lazy, triggered by a call,
   not by startup.

3. **The fourth injection flag.** `needs_mail` on `Tool`, and a fourth branch in `run()`.
   Write the docstring the way `needs_schedule` and `needs_library` are written — say why
   it is not a field on `Limits`. Follow the precedent; do not redesign the chain.

4. **One tool, end to end**, against a fake Gmail service. `gmail_search` is the right one
   — AC 17 is the list, and AC 23, AC 24 and AC 26 are its boundaries, so a single tool
   already exercises the empty case, the bounded case and the refused case.

5. **Tests for what exists.** Not for what does not.

## Two decisions this cycle has to make, not defer

**Where the token cache lives (AC 14).** Outside the repository, readable only by the
user. `.axiom/` is relative to the working directory and is therefore not a candidate.
Note the real obstacle rather than waving at it: **`os.chmod` does not restrict a file to
one user on Windows** the way it does on POSIX — the permission bits are largely ignored.
Either the home directory being user-scoped is accepted as the answer and *said so in the
code*, or it takes an ACL. Decide, write the reason down, and make the test assert
whichever was chosen.

**How the client id and secret are read.** Axiom's convention is `AXIOM_*` from the
environment (`config.py:259` onward), and `mcp.json` already has `${NAME}` substitution
that holds the *name* of a secret and never its value. Pick one and match it; do not
invent a third mechanism, and do not read a `client_secret.json` from a path frozen at
install time.

## The baseline, measured

**964 passed, 1 deselected, 129.25s**, on `master` at `3a6a351`, before anything in this
loop was written. Use it; do not spend a cycle re-measuring what has not changed yet.

The last handoff recorded ~140s against an earlier 107s and concluded from `--durations`
that it was machine state rather than a regression. 129s on a quiet machine says that
reading was right. **The goal's "no worse than ~140s" is therefore a soft ceiling with
about 10s of slack already in it** — three Google libraries at import time is exactly the
kind of thing that eats that, so measure after `uv sync` and say what it cost.

## What proves the cycle moved

`gmail_search` callable through `tools.run()` against a fake, returning a list a model can
read, with the empty and bounded cases covered. Suite green. The count in `logs/cycle-2.md`
names which criteria that actually backs — and it is a small number. **Do not claim a row
the fake did not exercise.**

First thing to tackle: **the branch, then `mail.py`'s class and the `needs_mail` branch in
`run()`.** The tool is worth nothing until something can be handed to it.

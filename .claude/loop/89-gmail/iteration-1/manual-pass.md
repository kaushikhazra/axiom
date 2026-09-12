# #89 — the manual pass

Fifteen rows the loop could not drive. Every one needs a real Google account, a real
browser, or the passage of time, and **none of them is claimed in any cycle log**.

Twenty-five of the forty are backed by tests and are not repeated here. The list of what
each test backs is in `logs/cycle-2.md` through `logs/cycle-6.md`.

## Before any of this can be driven

These are Kaushik's, not the loop's, and nothing below works without them.

| | |
|---|---|
| 1 | A Google Cloud project — new or existing |
| 2 | **Gmail API** enabled in it |
| 3 | OAuth consent screen: **External**, with `hazra.kaushik@gmail.com` added as a test user |
| 4 | An OAuth client of type **Desktop app** — this is the type that permits a loopback redirect. Not "Web application", which is what Google's own MCP docs specify and which needs a fixed HTTPS callback axiom does not have |
| 5 | `AXIOM_GOOGLE_CLIENT_ID` and `AXIOM_GOOGLE_CLIENT_SECRET` in the environment |

This is the **Gmail API directly**, not `gmailmcp.googleapis.com`. No Developer Preview
enrolment is needed.

**Run it outside the repository.** `C:/Projects/.tmp/axiom-manual`, as #74's pass did:

```
cd C:\Projects\.tmp\axiom-manual
uv run --project C:/Projects/axiom axiom
```

`--project`, not `--directory`. `--directory` moves the working directory into the repo,
which CLAUDE.md's tool-testing rule forbids.

## The seven-day expiry, before it is mistaken for a defect

**A Google app in "Testing" status expires every refresh token after exactly seven days.**
Not the access token — the refresh token. This is Google's policy for unverified apps and
it is accepted, not a bug.

What it does to this pass:

- **Row 9 (AC 12) becomes unprovable after day 7.** A silent renewal needs a refresh token
  Google will still honour.
- **Row 10 (AC 13) becomes easy**, where it would otherwise have to be forced. Waiting a
  week is the cheapest way to reach it.

If row 9 fails on day 8, the answer is to grant again — not to file anything.

## The rows

Drive them in order. Rows 1 to 6 are one sitting; the rest can be picked up separately.

### Granting

**Row 1 — AC 4, AC 5, AC 2.** Start axiom with the variables set. Ask *"what's in my
inbox?"*

- The startup line names **two more tools** than a run without the variables.
- Before the browser opens, axiom says Gmail is asking and that it will be able to **read**
  and cannot send, delete or change.
- The browser opens at **Google's own sign-in page**, not at anything axiom drew.

**Row 2 — AC 7, AC 6.** Sign in and grant.

- **Nothing is typed back into the terminal.** No code pasted, no URL copied.
- The browser returns to a page saying it worked, and the terminal **finishes the request
  that started it** — the inbox list appears in the same turn, not after another prompt.

**Row 3 — AC 21.** While row 2's request is in flight, watch the terminal.

- The call line names `search_mail` and the query before the result arrives.
- A transient `· search_mail ...` line sits under it and is taken back when the result
  lands.

**Row 4 — AC 8.** `/mail forget`, then ask for mail again, and **decline** at Google's
consent screen.

- The session is still running.
- axiom says permission was declined.
- Ask for something else — a web search — and it works.

**Row 5 — AC 9.** `/mail forget`, ask again, and **close the browser tab** without
answering.

- The session is still running and says Gmail is not available.
- **This is the row most likely to hang.** If the terminal is still waiting after three
  minutes, that is row 6 failing, not row 5.

**Row 6 — AC 10.** `/mail forget`, ask again, and **do nothing at all** for three minutes.

- The wait ends by itself at about 180 seconds.
- axiom says the browser was not answered in time.
- The session carries on.

### Remembering

**Row 7 — AC 3, AC 11.** Grant, `/exit`, start axiom again, ask for mail.

- **No browser opens.**
- The mail arrives.

**Row 8 — AC 14, in the place it actually lands.** After row 7, look at
`~/.axiom/gmail-token.json`.

- It exists, and it is **not** anywhere under `C:/Projects/axiom`.
- On Windows the mode says nothing; the location is the protection. Confirm the file is
  under `C:/Users/hazra` and nowhere else.

**Row 9 — AC 12.** Within seven days of granting: leave axiom idle past an access token's
hour, then ask for mail.

- It answers **without a browser opening**.
- Read the seven-day note above before recording a failure.

**Row 10 — AC 13, AC 34.** Either wait past day 7, or revoke axiom's access at
[myaccount.google.com/permissions](https://myaccount.google.com/permissions), then ask for
mail.

- axiom does **not** fail silently.
- It says the permission could not be renewed and points at `/mail forget`.
- After `/mail forget`, asking again opens the browser and the grant works.

### Reading

**Row 11 — AC 17, AC 18.** Ask for mail from a named sender, then ask to read one of them.

- The list carries **sender, subject and date** for each.
- The body arrives as readable text.

**Row 12 — AC 19, against real mail.** Read four messages chosen for their shape: a plain
one, an HTML newsletter, one with an attachment, and one forwarded several times.

- Every one arrives as text a person can read.
- No raw `<div>` or `<table>` anywhere.
- The five shapes are covered by tests; **this row is about mail nobody wrote a fake for.**

**Row 13 — AC 20.** Read a message with an attachment.

- The filename, its type and its size are named.
- The attachment is **not** downloaded — nothing new appears on disk.

**Row 14 — AC 22.** `/mail`.

- It names the account being read.
- It says nothing that looks like a token.

### What must not happen

**Row 15 — AC 27, AC 28, and the one worth the whole pass.** Ask the model, in plain
words, to **send an email**, then to **delete one**.

- axiom offers no tool that could.
- If the model improvises one anyway, the call fails as an unknown tool.
- Nothing is sent and nothing is deleted.

This is the row that proves the scope decision rather than the code: `gmail.readonly` is
the only permission ever requested, so even a model that found a way to ask would be
refused by Google rather than by axiom.

## What this pass cannot reach

**AC 39's browser half.** axiom opens the user's browser and cannot close it — that window
is the user's. The criterion is read as *axiom leaves no listener behind*, which
`test_the_flow_closes_its_listener_on_the_timeout_path` settles.

**A second Google account.** Nothing in #89 needs one; AC 20's two-servers-one-account
concern belongs to #82.

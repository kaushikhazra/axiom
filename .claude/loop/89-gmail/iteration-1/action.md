# Action

Cycle 3 wired the session, so `search_mail` is reachable by a model in a real run. Its
constraint: **a search returns ids nobody can open.** AC 17 hands the model a list and AC 18
is the tool that reads one, and without it the feature is a directory with no doors.

**Write `read_mail`. Nothing else.** The `/mail` command is the next cycle's.

## Before writing anything

`gh issue view 89`. Cycle 3 found two claims made against **#90's** numbering, and the only
reason it found them was reading the issue rather than trusting a copy. Do the same.

**Commit before breaking anything.** Cycle 3 lost eight edits to `git checkout --` on
uncommitted work — the exact failure `assumption.md` names. Knowing the rule did not
prevent it; committing would have.

## AC 19 is the row this cycle exists for

*"A message's body reaches the model as readable text whatever encoding it arrived in."*

The happy path is one shape and Gmail has several. Handle each, and **write a test per
shape** — a single "it decodes base64" test would claim the row while covering a fraction
of it:

| shape | what it is |
|---|---|
| `text/plain` single part | body in `payload.body.data`, base64url |
| `multipart/alternative` | plain and HTML siblings; take the plain one |
| HTML only | no plain part at all — strip it rather than hand the model tags |
| `multipart/mixed` with an attachment | the text part is nested under another part |
| nothing decodable | say so; do not return empty |

base64url, not base64 — `-` and `_` for `+` and `/`. `base64.urlsafe_b64decode` needs the
padding restored.

## AC 20 comes free if the walk is written right

*"A message that carries an attachment has that attachment named rather than dropped."*
The same recursive walk that finds the text part sees the attachment parts. Name them —
filename and size — the way `servers.as_text` names a block it cannot show, and for the
same reason: **a model told nothing came back answers from memory.** #40 is the precedent
and it is already cited in `search_mail`.

## AC 31 is a constraint on how this is written, not a feature

*"The body of a message is never written to disk by axiom."* Gmail's client offers
`get_media` and attachment downloads. Do not call them. The body is decoded in memory and
returned as a string, and the test that proves it should assert on what the fake was asked
for, not on the absence of a file.

## What proves the cycle moved

`read_mail` callable through `tools.run()` against a fake, with a test for each shape in
the table, an attachment named, and a message that cannot be decoded saying so. Full suite
green — **a full run, not a subset plus arithmetic.** Cycle 2's log got that wrong and
cycle 3's had to correct the correction.

First thing to tackle: **the recursive part walk**, because AC 19, AC 20 and AC 31 are all
the same function.

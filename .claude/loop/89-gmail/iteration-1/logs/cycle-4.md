# Cycle 4 — read_mail, and the shapes a body arrives in

2026-09-10. Branch `feature/89-gmail`. **1000 passed, 1 skipped, 1 deselected, 132.01s**,
full run, nothing else going.

## The count

**17 of 40**, from 13.

| newly met | how |
|---|---|
| **AC 18** | `test_a_plain_single_part_body_is_read` — an id from a list, a body back |
| **AC 19** | five tests, one per shape. See below |
| **AC 20** | `test_an_attachment_is_named_not_dropped` — filename, type and size |
| **AC 31** | `test_reading_never_fetches_an_attachment` |

## AC 19 was worth the five tests

The happy path is one shape and Gmail has several. Each has its own test because a single
"it decodes base64" would have claimed the row while covering a fifth of it:

| shape | test |
|---|---|
| `text/plain`, single part | `test_a_plain_single_part_body_is_read` |
| padding Gmail stripped | `test_padding_that_gmail_stripped_is_put_back` — every length 1 to 7 |
| `multipart/alternative` | `test_multipart_alternative_prefers_the_plain_half` |
| HTML with no plain sibling | `test_html_only_is_stripped_rather_than_handed_over` |
| text nested under `multipart/mixed` | `test_a_text_part_nested_under_a_mixed_part_is_found` |
| nothing decodable at all | `test_a_message_with_no_readable_part_says_so` |

**base64url with the padding stripped is what Gmail actually sends**, and
`urlsafe_b64decode` raises on it. The `=` arithmetic is not defensive
programming — without it, four of the six shapes fail.

**HTML is stripped with `trafilatura`**, which is already a dependency and already what
`fetch_page` uses. Handing a model raw markup spends the window on tags and teaches it to
quote them back. The fallback is a regex, then the raw text — a body that resisted
extraction is still the only body there is.

One walk, not two. AC 19 and AC 20 read the same tree, and a second pass would be a second
chance to disagree with the first.

## AC 31 is proved by what was asked for

*"The body of a message is never written to disk."* The test asserts the fake was asked for
exactly one `get` and nothing else — **not** that no file appeared. A test checking for the
absence of a file passes on a machine where the write silently failed, which is no evidence
at all.

An attachment's bytes live behind a separate `attachments().get()` that is never called.
The filename and size are in the part itself, which is all a model is given.

## The fake was too permissive, and that was caught

The first version put headers at the top level **and** under `payload`. Gmail puts them
under `payload` and nowhere else, so the fake would have passed whichever one the code
read. Removed, with a comment saying why. All 36 still pass — this time for the right
reason.

That is the same failure class as cycle 2's stale helper: a test artefact that is more
forgiving than reality is a green light with nothing behind it.

## Broken before claimed — three times

Committed **first**, after cycle 3 lost eight edits to exactly this.

| break | red |
|---|---|
| padding arithmetic removed | 5 |
| recursion removed from the walk | 4 |
| plain-beats-HTML preference removed | 2 |

Each restored from the commit. The third is the one worth having done: the preference could
have been wrong while every other test stayed green, because only two of the six shapes can
tell.

## Assumptions

None changed.

## Where this leaves the next cycle

Reading works end to end — a model can search, get ids, and open one. What has no code at
all is the **`/mail` command**: AC 15, AC 16 and AC 22, the only surface in this issue with
no precedent anywhere in axiom. `forget()` and `status()` exist and are tested; nothing
lets a user reach them.

After that the remaining rows are the flow itself (AC 4 to AC 13), the failure paths
(AC 32 to AC 35), the exit (AC 39, AC 40), and the AC 29/AC 30 sweep — which is reading,
not writing, and should not be left to the end.

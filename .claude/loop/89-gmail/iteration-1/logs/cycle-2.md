# Cycle 2 — the shape, and one tool

2026-09-10, 22:0x IST. Branch `feature/89-gmail`. First cycle that wrote.

## The count

**8 of 40 met**, from 0. Every one is backed by a test named below; nothing is claimed
that a fake did not exercise.

| met | how |
|---|---|
| **AC 1** | `test_nothing_configured_offers_no_mail_tool` — and the characterization baseline, which caught this failing before the test existed |
| **AC 2** | `test_configured_offers_the_mail_tools` |
| **AC 17** | `test_search_returns_sender_subject_and_date` |
| **AC 23** | `test_a_search_matching_nothing_says_so` + `test_nothing_configured_says_which_variables` |
| **AC 24** | both halves — `test_a_bounded_search_says_it_was_bounded` and `test_an_unbounded_search_does_not_claim_truncation` |
| **AC 26** | `test_an_empty_search_reaches_google_not_at_all` — asserts no call was made, not just that it refused |
| **AC 27, AC 28** | `test_the_only_scope_is_read_only`, `test_no_tool_can_send_or_delete` |
| **AC 14** | `test_token_lives_outside_any_repository`, and the mode on POSIX |

Partial, and **not counted**: AC 15/16 (`forget()` works and is tested, but there is no
`/mail` command to reach it — the criterion is about the user doing it); AC 29/30 (`_why`
is tested against a leaky exception, but the sweep has not been done); AC 37 (the guard
exists and is tested, but only through `Mailbox.interactive` — nothing yet sets it from
`isatty`).

## What the artifact caught that reasoning did not

The suite went red on `test_observable_behaviour_matches_the_baseline`: **12 tools where
the baseline says 11.** `search_mail` went into `REGISTRY` and `declarations()` returns
everything, so every model was offered a Gmail tool on a machine with no Google account.

That is AC 1, failing, caught by a guard written for something else. **The baseline was
not moved** — `tests/baseline/transcript.txt` is unchanged and the filter was written
instead. Moving it would have made the criterion pass by redefining what "as it does
today" means.

`test_switch.py`'s `ALL_TOOLS` then needed the same subtraction it already applies to the
skill tools. Its comment now carries both reasons.

## The measured cost of three dependencies

Three direct, **sixteen installed**: `google-api-core`, `googleapis-common-protos`,
`httplib2`, `oauthlib`, `proto-plus`, `protobuf`, `pyasn1`, `pyasn1-modules`, `pyparsing`,
`requests`, `requests-oauthlib`, `uritemplate` and the rest. `google-api-python-client`
alone is **15.3 MiB**.

**`googleapiclient.discovery` costs 1.196s to import**, measured with `-X importtime`.
`tools.py` imports `mail.py`, so a module-level import would have put 1.2s on every axiom
start, every test collection and every `--help`. Nothing is imported from Google at module
level; the imports sit inside the functions that need them, which is what `servers.py`
already does with `streamable_http_client`.

Worth naming for later: axiom now has **two HTTP stacks**. `httpx` for the web tools,
`requests`/`httplib2` underneath Google's client. Not a problem today, and not one to
solve by hand.

## The two decisions the cycle owed

**Where the grant lives.** `~/.axiom/gmail-token.json`, overridable with
`AXIOM_GOOGLE_TOKEN`. `.axiom/` was rejected because it is relative to the working
directory, which for a developer is this repository.

`0o600` is written, and **the docstring says what it is worth**: on POSIX it is the whole
answer; on Windows `os.chmod` moves the read-only bit and nothing else, so the mode says
nothing about who may read the file. What restricts it there is the location —
`C:/Users/<name>` is ACL'd to that user by Windows. That is the protection; `chmod` is
not. The test asserts the mode **only on POSIX** and says why rather than asserting
something false on Windows.

**How the credentials are read.** `AXIOM_GOOGLE_CLIENT_ID` and
`AXIOM_GOOGLE_CLIENT_SECRET`, matching `config.py`'s existing `AXIOM_*` convention. No
third mechanism, and no `client_secret.json` on a path frozen at install time.

## The constraint, resolved

`needs_mail` is the fourth flag and the chain stays exclusive. The docstring records
something cycle 1 only half-saw: injection is not merely tidy, it is **what makes AC 29
structural**. A credential that arrives by injection is never a declared argument, and
`run()` refuses arguments a tool did not declare — so a token cannot be a tool argument,
and therefore cannot reach `note_tool` and the screen.

## Broken before claimed

`without_unusable_mail_tools` was forced to `if True: return declarations`. **Five tests
went red** — the two new filter tests, the characterization baseline, and both switch
tests. Restored with `git checkout --`, after committing, per the standing rule.

## Suite

**986 passed, 1 skipped, 1 deselected.** 23 new tests. Wall clock measured in the next
cycle's log; the run after the filter landed was still going when this was written, and
the run before it was **128.14s** against a 129.25s baseline — so the three Google
libraries have cost nothing measurable, which is what the deferred imports were for.

## Assumptions

None changed.

## Where this leaves the next cycle

The shape holds and one tool sits on it. What is now missing is **the session** — nothing
builds a `Mailbox`, nothing passes it to `run()`, and nothing sets `interactive` from
`isatty`. `search_mail` is reachable from a test and from nowhere else.

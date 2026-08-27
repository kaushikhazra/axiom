# Cycle 2 — the cold read

2026-08-28 01:06–01:22 IST. Fail-safe 04:21 IST.

Criteria read from `gh issue view 57` **before** the diff and before cycle 1's log.
**473 tests, green and hermetic** (was 471). Transcript byte-identical. No stray `.axiom/`.

Not a genuinely fresh reader - no second agent - and `observe.md` asks that this be said rather
than a cold read claimed that was not cold.

## One finding, and it is the third time this shape has appeared

**`test_rubbish_is_still_reported_in_todays_words` passed for the wrong reason.**

AC 7 says a genuinely malformed file still reports a problem naming the file and the underlying
cause. The test asserted `"could not be read" in problems[0]`. But a *strict* decoder rejects
that same file at the mark, before the JSON is ever parsed, and reports:

```
could not be read (Unexpected UTF-8 BOM (decode using utf-8-sig): line 1 column 1 (char 0))
```

which contains `could not be read` just as happily. **The assertion was true whether the fix was
present or not.** It was one of the six that survived cycle 1's break, and cycle 1 counted it as
fine without checking why it survived.

With the fix, the message names the real fault - `Expecting property name enclosed in double
quotes: line 1 column 3`. So the test now asserts that, and asserts `BOM` is **absent** from the
message. The file must be refused for being rubbish, not for its encoding.

**Third instance of the same shape.** #48 AC 33 asserted `"saved choice"` and passed on a
sentence that was gibberish. #49 AC 25 and AC 27 were criteria read too loosely. All three are a
substring assertion that a wrong implementation also satisfies.

## The attacks that found nothing

Worth recording, because a clean result on a hostile input is evidence and a clean result on a
friendly one is not.

- **AC 4, on the paths cycle 1 missed.** A file whose *first* key is not `mcpServers`, with two
  servers, a `tools` list and an `env` map - a mark lands on whatever comes first, so this is
  where a text-level fix would show. Every value clean. Now a test rather than a probe.
- **AC 6, the awkward write.** `write_choice` on a file that is marked *and* malformed takes the
  replacement path, not the merge path - the one route where a mark could reach a file axiom
  wrote. Clean, and it also proves the file becomes readable afterwards. Now a test.
- **AC 9, beyond the grep list.** Searched `config.py` and `models.py` for `platform`, `win32`,
  `os.name`, `sys.plat`, `'nt'`, `posix`. One hit: the word "platform" inside a comment.
- **AC 7, AC 8 against the current source.** Cycle 1's hard-coded messages checked against the
  strings in `config.py` today, not against what its log claimed. Both match.

## The six that survive the break, each judged

Cycle 1 reported "12 red" in aggregate and did not name the six that were not. Named now, with
the fix reverted:

| test | verdict |
|---|---|
| `test_an_unmarked_file_still_reads` | **fine** - AC 2 is a *still works* criterion; this is the guard that the permissive decoder did not break the ordinary case |
| `test_axiom_writes_no_mark` | **fine** - the writer was never changed; guards a future change that makes it emit one |
| `test_rewriting_a_marked_and_malformed_file_leaves_no_mark` | **fine** - also about the writer, which is unchanged either way |
| `test_a_broken_choice_file_is_still_called_broken` | **acceptable** - `unreadable` returns a bool and exposes no reason, so there is nothing to distinguish. Unlike the rubbish test, there is no message that could be right for the wrong reason |
| `test_a_missing_file_is_not_called_broken` | **fine** - absent versus malformed, unrelated to encoding |
| `test_nothing_about_the_decoding_branches_on_the_platform` | **fine** - AC 9 is a source-level fact and passes by design |

None vacuous. All six are *still*-or-guard assertions, which are supposed to hold before and
after.

**After the fix to the rubbish test, the break turns 14 red rather than 12.**

## Status — all 9 criteria

| criteria | status |
|---|---|
| AC 1–9 | `met-with-evidence` |

Each has a test in `tests/test_encoding.py` citing it by number. AC 9 is settled by a source
grep rather than by behaviour, because a test cannot see a branch that only fires on a platform
it is not running on.

## Exit

Converged - `loop.md` exit 1. Commit, push, PR referencing #57, merge, delete the branch. Then
mark row 11 done, scaffold row 12 (#55), mark it running. **The cron is not touched.**

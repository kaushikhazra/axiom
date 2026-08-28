# Cycle 3 — 2026-08-28 20:08 +0530 — GOAL MET

The four criteria that needed the full output path rather than the renderer. All four hold.

## Where the artifact stands

**Levels collapsed: 0. Lines that are not one line: 0.** Unchanged from cycle 2, and now
confirmed against the plain path as well as the rendered one.

**AC 13 — the structure matches the markdown the model wrote.** Normalised to levels rather
than columns, `- one / - two / - three / - back to two / - back to one` renders as
`[0, 1, 2, 1, 0]`, which is exactly the shape of the source. This is the only criterion in
the issue that can find a *wrong* answer rather than a missing one, and it is the one that
would catch the depth stack disagreeing with the source rather than merely losing something.

**AC 11 and AC 12 — the plain path is byte for byte the markdown.** Structurally rather than
by luck: `show_piece` returns before `Rendered` exists when rendering is off or output is not
a terminal, so nothing this issue changed is reachable from there. Tested by feeding a nested
reply four characters at a time and comparing the captured output to the input exactly.

**AC 9 — deeper than the window is wide.** Measured before deciding what to do, as
`action.md` required. Eight levels against a **20-column** window: every one of the eight
items survives whole. The rows are wider than the window and the terminal wraps them, which
is right - a nested item's text goes through the paragraph path, so nothing crops it. No
change was needed and none was made.

`action.md` said to stop if AC 9 turned out to need #72's crop fix. It did not.

## The breaks

Two, both precise:

- **Nesting disabled** (`if True: return None`) - **11 distinct tests red**, including both
  of this cycle's feature tests. Notably `test_a_list_nested_deeper_than_the_window_keeps_every_item`
  fails too, which was not obvious: flattening reinstates the four-space code block, and the
  container crops the text. So AC 9's test is not vacuous even though AC 9 needed no code.
- **The plain path bypassed** (`if False:` in `show_piece`) - **5 tests red**, including this
  cycle's two byte-for-byte tests and three that already existed. The plain path is genuinely
  guarded.

No vacuous tests found this cycle. Cycle 2 found three of eleven; this cycle's five were
written knowing that, and each was checked against a break before being counted.

## Criteria — 13 of 13

**Met, with a test shown to fail when the fix is reverted: 11** - AC 1, 2, 3, 4, 5, 6, 8, 9,
11, 12, 13.

**Met, guarded, and correctly not break-sensitive: 2** - AC 7 (markup inside a nested item)
and AC 10 (a sub-item with no parent is shown). Both have tests; both pass whether or not
nesting works, because both are about properties that must hold *either way*. A regression
guard that failed when the feature was removed would be testing the wrong thing.

That distinction is why the goal check is being read as met rather than as 11 of 13.
`observe.md` asks that each new test fail when the fix is reverted; two of them do not, and
the reason is recorded here rather than being fixed by making them into something they are
not.

## Suite

`uv run pytest` - **635 passed in 74.40s**. Baseline on this branch was 630; 5 added. Green
and hermetic.

## Goal check: MET

Every criterion in #73 holds. Levels collapsed is zero. Renderings that are not one line is
zero. A flat list is unchanged and guarded by a test proven to fail when a bullet moves two
columns. The suite is green.

**The loop ends. The cron is deleted.**

Three cycles: measure, fix, finish.

## Assumptions

None changed across the whole iteration. The cause recorded in `assumption.md` at the start -
one line rendered in isolation, with the seam in `Rendered` rather than `_as_markdown` - was
right, and the fix is the one cycle 1 predicted from it.

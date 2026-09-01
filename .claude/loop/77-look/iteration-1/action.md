# Action — cycle 3

Stage 2 of the build order: **the model chooser.** AC 1 to 6.

The accent constant, the theme seam and the `NO_COLOR` path are settled and proved
by stage 1. This stage draws a panel with them.

## Do these in order

1. **Read `.tmp/mock_chooser.py` before writing.** It is the agreed design and it
   already resolves the things that are easy to get wrong: the panel geometry,
   right-aligned numbers, the `tools` annotation only on a mixed host, and
   `"dim default"` rather than `"dim"` on anything inside a panel — a bare `dim`
   inherits the border's accent and comes out tinted.

2. **Rewrite `list_models` in `terminal.py` to draw a panel.** The title carries
   **`models on <host>` whole** — not a `models` title with the host as a subtitle.
   Ten assertions match that phrase and four of them are negatives that go quiet
   rather than red if it is shortened. Leave a comment saying so, at the title.

3. **Align the columns.** Names pad to the longest, so `tools` and `(default)`
   line up down the list. This is the decision that costs 11 assertions, and it
   is Kaushik's, already taken — do not re-open it.

4. **Re-point the 11 adjacency assertions** in `test_models.py`, `test_switch.py`
   and `test_tools_first.py`. They match `"gemma4:e2b  tools  (default)"` and
   friends by exact spacing. Re-point them; do not loosen them into
   `"gemma4:e2b" in out` — a test that stops caring where the marker sits is not
   a re-pointed test, it is a deleted one.

5. **`ask_model` keeps its wording.** `which model? (enter for the default)`.
   Seven assertions match it and the design does not change it.

## Prove, do not claim

For each of AC 1 to 6: **break it and watch the test go red.** `.tmp/break_stage1.py`
is the harness — copy its shape, it applies each break to a copy of the file and
restores it.

**AC 6 — a window too narrow still shows every model's name in full — is the one
that will pass while testing nothing.** Two cycles running, a first-time pass on a
boundary criterion has been hollow. A panel has a border and padding, so the text
gets less room than the window; write the case that would crop and check the name
survives it.

**AC 4 needs all three hosts**, not one: some models capable, all capable, none
capable. The middle and the last are where a marker appears that should not.

## Do not

- Touch the info panel, the voice, the tool summary or the prompt. That is stage 3.
- Touch `tests/baseline/transcript.txt`. The chooser is not in it. **If it moves,
  that is the finding.**
- Add a second accent constant. `terminal.ACCENT` exists.

## Record

`logs/cycle-3.md`, per `observe.md`. Criteria met out of 37, the suite count and
wall-clock, and whether the baseline is untouched.

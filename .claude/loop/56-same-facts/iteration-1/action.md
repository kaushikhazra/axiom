# Action

**Cycle 1 records the baseline, reproduces both gaps, fixes them, and covers the twelve.**

## 1. Baseline

- `env AXIOM_HOST=http://127.0.0.1:1 AXIOM_MODEL=nonsense:99b AXIOM_DEBUG_MAX_CONTEXT=7 uv run pytest -q`
  Expect **490 passed**. Record it.
- Copy `tests/baseline/transcript.txt` to `.tmp/transcript-baseline-56.txt`.
- `gh issue view 56`, record all 12 criteria `not-started`.

## 2. Enumerate before fixing

List what `announce()` reports today - model, host, context, override note, tool count, web
state - and mark each **belongs on the switch line** or **excluded, and why**. That list *is*
AC 4, and writing it first stops the row being read as "the two facts already named".

## 3. Reproduce both, before touching src

Two failing tests, each with **two settings**:

- Web on and `--no-web`: the switch line must distinguish them. Today both say `N tools`.
- Override in force and not: the switch line must distinguish them. Today both say `N tokens`.

**Watch them fail.**

## 4. Fix

`note_switched` gains the web state and the override note. `_switched_to` already has
`settings` in scope.

**Decide and record**: share a helper with `announce()` so the phrasings cannot drift, or
duplicate them. If duplicated, the agreement tests below are the only thing holding them
together - say so in the log.

## 5. Cover the twelve, comparing the lines against each other

- **AC 5 to AC 8** - for each state (cannot call tools, tools off, web on, web off, context
  unknown), run one session that starts in that state and switches within it, then assert the
  **switch line carries the same facts as the startup line**. Parse both from the same run.
  Never hard-code the wording on both sides.
- **AC 9** - with an override in force, the switch line must differ from what the same model
  prints without one.
- **AC 10** - two runs, same tool count, different web setting, distinguishable lines.
- **AC 11** - the host is absent from the switch line.
- **AC 12** - #49's behaviour is untouched; the existing suite is the evidence.

## 6. The transcript

It will change if any scenario switches models. **Fix every stub first**, regenerate
deliberately, read the whole diff, check `grep -c "^<"`. Account for every changed line.

## 7. Then

Full suite and the hermeticity command. Break the fix and record how many go red **and name the
survivors**. Write cycle 2's action: a cold read of all 12 from GitHub, before the diff and
before this log.

## Record

Status for all 12. The `announce()` enumeration with a verdict per fact. The failing-test-first
evidence. The share-or-duplicate decision. The break count and survivors. Every transcript line
that changed and why.

**Write no questions into anything.** Decide, record the decision and the reasoning under a
heading that says so, carry on. The exception is safety, not uncertainty.

# Cycle 1 — baseline and shape

2026-08-27 13:52–14:05 IST. Fail-safe 16:52 IST. **No production code written.**

## Baseline

- **377 tests, green and hermetic.** Branch `feature/49-model-switch` at `dfcf9a3`.
- Golden transcript copied to `.tmp/transcript-baseline-49.txt`.
- All 34 criteria recorded `not-started`.

## What a switch changes, and what it must not

`_chat`'s locals, each marked. This table is most of AC 10 to AC 17.

| local | on switch | criterion |
|---|---|---|
| `model` | **rebound** | AC 4, AC 6 |
| `capable` | **rebound** | AC 16 |
| `declarations` | **rebound** | AC 16 |
| `callable_names` | **rebound** | AC 16 |
| `effective_context` | **rebound** | AC 15 |
| `chat_options` | **rebound** | AC 15 |
| `messages` | untouched | AC 10, AC 11, AC 12 |
| `limits` | untouched | AC 13 |
| `attached` | untouched | AC 14 |
| `instructions` | untouched | AC 13 |
| `running_usage` | **reset to None** | named by no criterion — see below |

### Decision — `running_usage` resets to None on a switch

It is the previous turn's real `prompt_eval_count + eval_count`, and compaction triggers on it.
After a switch **it came from a different model's tokenizer**, and it is being compared against
the new model's window. Carrying it means the first turn on the new model decides whether to
compact using a number the new model never produced — too small a number against a smaller
window suppresses a compaction that was needed.

`None` is exactly the state a first turn is already in, and `maybe_compact` already handles it:
the measurement-driven `too_large` check still runs, so nothing is unguarded. Reset is the
option that is both reversible and already exercised by every first turn in the suite.

## Shape decision 1 — a `Running` dataclass, not six rebindings

Six locals move together and always for the same reason. A helper cannot rebind a caller's
locals, so the options were a nested function closing over `_chat`, inline handling, or one
object.

**One frozen dataclass holding the six**, built by a function taking a model name. `_chat`
then holds `run = _prepare(...)` and a switch is `run = _prepare(...)` again — one assignment,
and it is impossible to update five of six by accident, which is the failure mode inline
rebinding invites. Startup uses the same function, so the two paths cannot drift.

## Shape decision 2 — the switch reuses #48's pieces, with a sibling for the question

`models.sorted_models`, `models.picked` and `terminal.show_models` are called directly. **AC 2
is only cheap because they exist**, and a second sorting implementation is precisely how two
lists drift apart.

`_settle_model` itself is **not** reused. Four of its behaviours are wrong here: it exits the
process on a bad host (AC 30 says carry on), it treats Ctrl-C as leaving (AC 26 says cancel),
it marks the remembered model (AC 3 says mark the current one), and it can settle without
asking. A sibling `_switch_model` shares the pieces and not the policy.

## Decision — an ambiguity the criteria do not settle

**MCP servers are started only when the first model can call tools.** So a session that begins
on `gemma2:2b` has none running. AC 16 then says switching to a capable model "restores them,
and says how many" — but there is nothing to restore.

Two readings. Start every configured server at launch regardless of the first model, which
makes AC 14 trivially true; or start them lazily on the first switch to a capable model.

**Taking the lazy start.** The first option changes #43's behaviour for every existing user and
spends subprocesses a tool-less session will never use. The second preserves #43 exactly, and
AC 14 stays true because nothing already running is touched — starting something that was never
started is not restarting it.

`Servers.start()` spawns a thread and is **not idempotent** — a second call raises
`RuntimeError: threads can only be started once`. It gains a guard. Verified no test asserts
the current no-start-for-an-incapable-model behaviour, so neither reading breaks the suite;
this is chosen on merit rather than on what compiles.

## Probe — what a tool round leaves in history

Driven with a stub rather than a live model, deliberately: the shape is **axiom's**, not the
model's, so a live probe would add nondeterminism and prove nothing extra.

```
{'role': 'user',      'content': 'read x.txt'}
{'role': 'assistant', 'content': '', 'tool_calls': [{'function': {'name': 'read_file', ...}}]}
{'role': 'tool',      'content': 'error: No such file...', 'tool_name': 'read_file'}
```

**That is what AC 11 must carry into a model that cannot call tools** — an `assistant` message
carrying `tool_calls`, and a `tool` message carrying `tool_name`. Neither is removed, rewritten,
or collapsed. The test asserts these exact messages are still in the payload after a switch to a
model with `supports_tools` False.

## Status — all 34 criteria

| criteria | status |
|---|---|
| AC 1–34 | `not-started` |

## Cycle 2 will

1. `Running` and `_prepare`, refactoring startup onto them first so the two paths share code
   from the beginning rather than being reconciled later.
2. `/model` and `/model <name>`, reusing `models.picked` and `terminal.show_models`.
3. `_switch_model`, the announcement, and the guarded lazy server start.
4. Remembering, which is `_remember` unchanged.
5. The carried-conversation fit check.
6. The transcript last, and **only after every stub is fixed** — #48 wrote a golden master full
   of `AttributeError` by regenerating first.

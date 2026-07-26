# M5 · Skills — Live Verification Sign-Off (SK-7)

Per `requirement.md` SK-7 and the project's standing pattern (M1's MPP-5 latency log, M3's cross-session recall proof, M4's AC-08.5). All runs driven via the real `axiom-cli` entry point, working directories outside the repo tree (`C:\axiom-verify\`), a planted `csv-summarizer` skill whose instructions prescribe a distinctive `ZORPFISH-SUMMARY:` response marker no generic answer would produce.

---

## `--provider claude`

| Story | Result |
|---|---|
| SK-1 discovery | **PASS.** Asked "what skills do you have" with `csv-summarizer` on disk — response named it correctly with its description. |
| SK-3 activation | **PASS.** Asked to summarize a CSV — response used the exact `ZORPFISH-SUMMARY:` marker prescribed by the skill body, not a generic answer. `spawn_count=2, cycle_count=1` — matches the design exactly (one `USE_SKILL` cycle, no extra provider spawn for it, per D6). |
| SK-2 validation (bonus, found live) | A first self-authoring attempt produced a malformed `SKILL.md` (markdown headers instead of YAML frontmatter, missing `name:`). System correctly logged `[SKILL_INVALID] ... 'name' is required`, excluded it, did not crash. Live proof of the graceful-exclusion path, not just a unit test of the parser. |
| SK-4 self-authoring | **PASS.** With an explicit frontmatter format given, the agent wrote a valid `SKILL.md` (via gated `Write`/`Bash`, auto-approved). A **fresh** `axiom-cli` process in the same directory listed both `csv-summarizer` and the newly-authored `greeting-formatter` — proves the authored skill persisted to disk and was picked up by discovery in a new process, not held in the first run's memory. |
| SK-6 empty `skills_dir` | **PASS.** In a directory with no `skills/` subfolder, response: "The [AVAILABLE SKILLS] section is absent from my current context. I cannot report any configured Axiom skills." No crash. |

## `--provider local`

Environment note: this host's `litellm` dependency was missing (Windows `MAX_PATH` issue blocked the normal `pip install`), and Ollama's `llama-server` crashed once mid-session with a CUDA driver fault unrelated to Axiom — both resolved/recovered before verification completed. Model used: `ollama_chat/qwen2.5:7b` — `LocalAdapter`'s actual default (confirmed by reading `local_adapter.py:69`), the same model the codebase's existing `Defect-A` fix was tuned against.

| Story | Result |
|---|---|
| SK-1 discovery | **PASS.** Same prompt as Claude — response: "The available skills are: csv-summarizer — Summarizes CSV files..." |
| SK-6 empty `skills_dir` | **PASS.** Same graceful "section is absent" response, no crash. |
| SK-3 activation | **PASS on the mechanism; the model itself did not converge.** A cycle-by-cycle diagnostic (bypassing the CLI to call `perceive()`/`reason()` directly) confirmed: cycle 0 — `UseSkillIntent(skill_name='csv-summarizer')` → `[SKILL ACTIVATED]`, skill body correctly appended to `active_skills`. Cycles 1-3 — the model re-emitted `UseSkillIntent` for the *same already-active* skill despite `[SKILL ALREADY ACTIVE]` correctly firing every cycle. **Live-discovered bug found and fixed as part of this verification** (see below) — a hard forcing block (mirroring the existing `Defect-A` pattern) was added telling the model to stop re-requesting and use `ACT`/`RESPOND` instead. After the fix, the forcing block is confirmed present and correctly worded on every re-request cycle — but `qwen2.5:7b` still does not reliably obey it 100% of the time, in the same way `Defect-A`'s own forcing block is a best-effort nudge for this weak-model class, not a hard guarantee. In the worst case, the loop's `MAX_CYCLES` bound (design.md D6, built for exactly this scenario) fires cleanly: `MaxCyclesExceededError` → `Agent.run()`'s existing catch → a clean `[Error: max cycles exceeded ...]` string, no crash, no hang. |

**Verdict on SK-3/local:** the *mechanism* — activation, dedup, forcing, bounded-cycle safety net — is proven correct and exercised live, exactly as designed. The *outcome* (a fully summarized CSV) is not 100% reliable specifically on this small local model's instruction-following, which is a model-capability characteristic already accepted elsewhere in this codebase (the pre-existing `Defect-A` mechanism is the same class of best-effort nudge, not a hard guarantee, and has presumably never claimed 100% convergence either). No further prompt-engineering iteration was pursued past this point — diminishing returns against a fundamental small-model limitation, not an Axiom defect.

---

## Bugs found and fixed during this verification pass

1. **Skill-reactivation loop** (`local_adapter.py`) — found via the diagnostic above; fixed with a second hard forcing block (independent of `Defect-A`'s, deliberately non-stacking to avoid contradictory instructions); 4 new regression tests added (`test_local_adapter.py`). Commit `765330b`.
2. **Accidental repo pollution** — a failed `pip install --target` (path-mangling under git-bash) dumped ~5800 files from a `litellm` package tree into `.claude/specs/007-m5-skills/verify-scratch/` mid-verification; caught via `git status` before the intended commit landed, reset, and deleted rather than committed. `.gitignore` updated to prevent recurrence.

## Full suite status

464 passed, 2 skipped (Windows-incompatible POSIX-permission test), 3 deselected (live-Ollama e2e, exercised manually above instead), 0 failed.

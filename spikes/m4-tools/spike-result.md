# M4 Tools spike — `can_use_tool` vs `PreToolUse` hook

**Date:** 2026-07-23
**Environment:** `claude_agent_sdk` 0.1.56 (Python), `claude` CLI 2.1.216, Windows, run from inside an active Claude Code (VS Code extension) session.
**Question:** M4's design initially planned to gate the Claude (KIND-B) provider's destructive tool calls via `ClaudeAgentOptions.can_use_tool` — a documented, type-confirmed per-call permission callback (`claude_agent_sdk/types.py`). Does it actually intercept calls in practice?

## Finding

**No — `can_use_tool` never fired, under any configuration tested.** `PreToolUse` hooks did, reliably, and denial via a hook let the query complete gracefully (no crash, no uncaught exception).

### What was tried against `can_use_tool` (all failed to intercept)

1. `allowed_tools=["WebSearch"]`, `can_use_tool` set, `permission_mode="default"` — Bash executed unconditionally; callback never invoked.
2. Same, plus `setting_sources=["project"]` (attempting to exclude the "user" settings source, since `~/.claude/settings.json` on this machine has `skipDangerousModePermissionPrompt: true`) — same result.
3. Same, with the suspect `CLAUDE_*`/`CLAUDECODE` environment variables stripped from the parent shell before spawning Python (ruling out env-inheritance from the outer Claude Code session) — same result. (Also confirmed the SDK itself already strips `CLAUDECODE` and forces `CLAUDE_CODE_ENTRYPOINT=sdk-py` regardless of inherited env — `_internal/transport/subprocess_cli.py`, referencing upstream issue #573 — so environment inheritance was never the mechanism.)
4. No `allowed_tools` at all, `can_use_tool` unconditionally denying **every** tool call, `setting_sources=[]` — `probe_can_use_tool.py` in this directory is exactly this configuration. Bash still executed and returned the correct (unguessable) marker string; `callback_log.txt` stayed empty.

Root cause not fully isolated (most likely `skipDangerousModePermissionPrompt: true` in this machine's global `~/.claude/settings.json`, or some other ambient bypass specific to this environment) — but the practical conclusion holds regardless of root cause: **`can_use_tool` cannot be relied on** as the sole gating mechanism, at least not without a guarantee about the operator's global Claude Code settings that Axiom has no way to enforce or even detect.

### What was tried against `PreToolUse` hooks (worked)

`probe_pretooluse_hook.py` in this directory: a `PreToolUse` `HookMatcher` on `"Bash"` returning `{"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny", ...}}`. Result:

- The hook **fired** (logged to `hook_log.txt`, confirmed non-empty).
- The Bash call was **blocked**.
- The query still completed with `ResultMessage.is_error=False` — Claude explained in its own text response that the tool was blocked by a `PreToolUse` hook, rather than the query erroring or hanging.

This matches the SDK's own documentation (`code.claude.com/docs/en/agent-sdk/permissions`, "How permissions are evaluated"): hooks are evaluated **first**, before deny rules, ask rules, permission mode, and allow rules — "a hook deny applies even in `bypassPermissions` mode." The docs explicitly recommend this: *"For checks that must run on every tool call, use a `PreToolUse` hook instead."* M4's design follows that recommendation directly, now with empirical confirmation it actually works in the environment M4 will be verified in.

## Consequence for the design

`design.md` §9 (KIND-B wiring) and Decision D3 use a `PreToolUse` hook (`ClaudeAgentOptions.hooks`), not `can_use_tool`. `can_use_tool` is not used anywhere in the M4 implementation.

---

## Addendum (2026-07-24): `permission_mode` is load-bearing, not merely permissive

**Question:** During live-CLI verification of the finished M4 implementation (not just the spike), a hook-approved `Bash`/`Write` call was observed to silently fail to execute — Claude's own text response described the failure as coming from "the environment" or "the sandbox," even though the Guardrails GATE's own debug log showed `[GUARDRAILS_APPROVED]`. The hook had said yes; the call still didn't happen. Does `ClaudeAgentOptions.permission_mode` matter for whether a hook's `{}` ("no objection") decision actually results in execution?

**Finding: yes.** `probe_permission_mode.py` in this directory isolates it:

| `permission_mode` | Hook returns `{}` (approve) | Hook returns `deny` |
|---|---|---|
| default (unset) | Tool call does **not** execute (silently) | Blocked (as expected) |
| `"bypassPermissions"` | Tool call **executes** | Still blocked (hook deny overrides `bypassPermissions`, as documented) |

Reproduced output (2026-07-24):

```
=== default permission_mode (permission_mode=None) ===
[hook] fired for Bash -- returning {} (approved)
TEXT: Blocked — output redirection to that path was denied by the sandbox. The file wasn't created.
FILE NOT CREATED

=== bypassPermissions (permission_mode='bypassPermissions') ===
[hook] fired for Bash -- returning {} (approved)
TEXT: Done.
FILE CREATED, contents='ok'
```

A second probe (ad hoc, not committed as a separate file — reproduced inline above) confirmed the other direction: with `permission_mode="bypassPermissions"` set, a hook returning an explicit `deny` payload for `Bash` still blocks the call and no file is created — matching the SDK docs' claim that "a hook deny applies even in `bypassPermissions` mode." What the docs don't make explicit is that `bypassPermissions` is *required*, not just permitted, for a hook's affirmative "no objection" to actually take effect under this SDK version — without it, `{}` is closer to a silent no-op than a "continue to normal evaluation, which will probably allow it" as the docs' plain-language description implies.

**Consequence for the design:** `ClaudeAdapter.act()` (`design.md` §9, Decision D5) sets `permission_mode="bypassPermissions"` alongside the `PreToolUse` hook. This is safe specifically because the hook is the actual enforcement point and a hook `deny` overrides `bypassPermissions` — the mode change doesn't weaken the gate, it's what makes the gate's "yes" decisions actually take effect instead of being silently swallowed by an unrelated stricter default.

## Reproduce

```bash
cd spikes/m4-tools
python probe_can_use_tool.py      # callback_log.txt stays empty; Bash runs anyway
python probe_pretooluse_hook.py   # hook_log.txt shows the hook fired; Bash is blocked
python probe_permission_mode.py   # {} only executes under permission_mode="bypassPermissions"
```

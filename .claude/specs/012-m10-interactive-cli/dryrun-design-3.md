# Design Dry-Run Report #3

**Document**: `.claude/specs/012-m10-interactive-cli/design.md`
**Reviewed**: 2026-07-28

---

## Critical Gaps (must fix before implementation)

### [C1] `Agent.TurnResult` (core) references `CanvasBlock` (interface layer) — a reverse-dependency layering violation

- **Pass**: Pass 3 (Interface Contract Validation), cross-checked against this project's own architecture principle
- **What**: §3's `TurnResult` dataclass (defined in `src/axiom/agent.py`, the core composition root — placed *outside* the `interface/` tree in §1's own Module Layout diagram) has a field `tool_canvas_blocks: list[CanvasBlock]`. `CanvasBlock` is defined in `src/axiom/interface/web/canvas_routing.py` (§8) — an interface-layer module. For `agent.py` to construct `CanvasBlock` instances (as §3's `_execute_turn()` code sample does: `CanvasBlock.from_tool_result(name, result)`), it would have to `import` from `axiom.interface.web.canvas_routing` — a **core module importing from the interface layer**, backwards from every other dependency in this design and in the existing codebase (`interface/cli.py`'s own header comment: "Never imports loop, adapter, persona, or observability directly. Imports axiom.agent only" — interface depends on core, never the reverse). This also means `axiom-cli`'s existing, unmodified import graph would transitively pull in `axiom.interface.web` (and its FastAPI/CopilotKit-adjacent dependencies) just by importing `axiom.agent`, the opposite of D1/D2's own reasoning for keeping the web stack a separate, optional layer.
- **Risk**: If implemented as written, either (a) `agent.py` gains an import from `axiom.interface.web`, silently coupling the CLI's dependency footprint to the web stack and violating this project's package-per-component/core-stays-framework-free convention (the same convention D1 explicitly invoked to justify hand-emitting `ag-ui-protocol` events rather than depending on a heavier framework), or (b) an implementer notices the layering conflict mid-build and has to improvise a fix unreviewed by this dry-run.
- **Fix**: `TurnResult` carries raw core types only — `tool_outputs: list[tuple[str, ToolResult]]` (`ToolResult` already lives in `axiom/tools/port.py`, core-side, and `agent.py` already imports from `axiom.tools.guardrails`, so this is consistent with its existing import graph). The `write_file`/`run_shell` filter and the `CanvasBlock.from_tool_result()` conversion move from `Agent._execute_turn()` into `agui_bridge.stream_turn()` (§4), which already imports `canvas_routing.py` and is squarely interface-layer code. This is a strictly better separation of concerns too: canvas-routing *policy* (what counts as "canvas-worthy") is a UI concern, not something the core `Agent` should decide.

---

## Warnings (should fix, may cause issues)

None.

---

## Observations (worth discussing)

None.

---

## Summary

| Critical | Warnings | Observations |
|----------|----------|---------------|
| 1        | 0        | 0             |

**Verdict**: FAIL — needs revision

Reports #1 and #2's findings remain fully resolved (re-checked, not just assumed). This is a new finding surfaced by a fresh layering audit of §3's `TurnResult` against §1's own Module Layout — narrow in scope (one field's type, one conversion call moved to the correct layer), not a rework of the surrounding mechanism.

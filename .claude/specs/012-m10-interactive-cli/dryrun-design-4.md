# Design Dry-Run Report #4

**Document**: `.claude/specs/012-m10-interactive-cli/design.md`
**Reviewed**: 2026-07-28

---

## Critical Gaps (must fix before implementation)

None. Report #3's finding (C1 — `TurnResult` referencing the interface-layer `CanvasBlock` from core `agent.py`) is resolved: `TurnResult` now carries only raw `ToolResult` tuples (core-side, already in `agent.py`'s import graph); the `write_file`/`run_shell` filter and `CanvasBlock` conversion moved to `agui_bridge.stream_turn()` (interface-side). Re-verified end-to-end: `agent.py` has zero references to any `axiom.interface.*` symbol anywhere in the document. Two stale references to the old field name (`tool_canvas_blocks`) left over from that rename — one in `CanvasBlock.from_tool_result()`'s comment, one in the Error Handling table — were also found during this pass and fixed (both cosmetic/documentation-only; neither affected the actual data flow, which was already correct).

---

## Warnings (should fix, may cause issues)

None. Report #2's finding (W1 — unguarded double-submit on `/api/approval/{approval_id}`) remains resolved and correctly reflected in both §5's code sample and the Error Handling table.

---

## Observations (worth discussing)

None. Report #1's finding (O1 — single-process deployment constraint for the in-memory approval registry) remains documented in §2 and cross-referenced from the Error Handling table and Future Work.

---

## Pass 9: Design-to-Task-to-AC Traceability

#### Traceability Matrix

| File/Prescription | Task Reference | AC Reference |
|-------------------|---------------|--------------|
| `src/axiom/agent.py` — TurnResult, run_turn/end_session/set_provider, ConductorProxy + tool-output wiring | task.md row 1 | US-01 (AC-01.1–AC-01.3), US-05 (AC-05.2), US-06 (tool-output collection) |
| `src/axiom/router/router.py` — set_forced_provider() | task.md row 2 | US-05 (AC-05.2) |
| `src/axiom/router/conductor_proxy.py` — ConductorProxy | task.md row 3 | US-05 (AC-05.2) |
| `src/axiom/tools/registry.py` — on_result callback | task.md row 4 | US-06 (AC-06.1) |
| `src/axiom/providers/local_adapter.py` — threads on_result | task.md row 5 | US-06 (AC-06.1) |
| `src/axiom/interface/web/__init__.py` — package init | task.md row 6 | US-07 |
| `src/axiom/interface/web/server.py` — FastAPI app + routes | task.md row 7 | US-02 (AC-02.1), US-03 (AC-03.1–.4), US-04 (AC-04.1), US-05 (AC-05.1–.3) |
| `src/axiom/interface/web/session_manager.py` — WebSession | task.md row 8 | US-01 (AC-01.1–.3), US-03 (AC-03.2) |
| `src/axiom/interface/web/agui_bridge.py` — stream_turn() | task.md row 9 | US-02 (AC-02.1–.3), US-03 (AC-03.2–.3), US-06 (AC-06.1–.2) |
| `src/axiom/interface/web/approval_bridge.py` — approval_fn | task.md row 10 | US-03 (AC-03.1–.3) |
| `src/axiom/interface/web/canvas_routing.py` — CanvasBlock/split_for_canvas | task.md row 11 | US-06 (AC-06.1–.2) |
| `src/axiom/interface/web_cli.py` — axiom-web entry point | task.md row 12 | US-07 (AC-07.1) |
| `pyproject.toml` — script + deps | task.md row 13 | US-07 |
| `scripts/tray_launcher.py` — pystray launcher | task.md row 14 | US-07 (AC-07.3) |
| `web/package.json` — Vite+React+TS+CopilotKit | task.md row 15 | US-07 |
| `web/vite.config.ts` — PWA plugin config | task.md row 16 | US-07 (AC-07.2) |
| `web/public/manifest.json` — PWA manifest | task.md row 17 | US-07 (AC-07.2) |
| `web/src/App.tsx` — layout + chrome | task.md row 18 | US-01, US-06, US-07 |
| `web/src/theme.css` — design tokens | task.md row 19 | US-07 (AC-07.4) |
| `web/src/components/ApprovalPrompt.tsx` | task.md row 20 | US-03 (AC-03.2) |
| `web/src/components/TracePane.tsx` | task.md row 21 | US-04 (AC-04.1–.4) |
| `web/src/components/CanvasPane.tsx` | task.md row 22 | US-06 (AC-06.1, AC-06.3) |
| `web/src/components/ProviderSelector.tsx` | task.md row 23 | US-05 (AC-05.1, AC-05.3) |

**Result**: All 23 file-level prescriptions traced to tasks and ACs. No traceability gaps.

---

## Summary

| Critical | Warnings | Observations |
|----------|----------|---------------|
| 0        | 0        | 0             |

**Verdict**: PASS

Four iterations: Report #1 found the core architectural gap (mid-turn events had no delivery mechanism, with knock-on effects on canvas and provider-visibility), Report #2 found one small concurrency edge case surfaced while re-verifying the fix, Report #3 found a layering violation introduced by the Report #1 fix itself (core `agent.py` reaching into the interface layer). Report #4 finds nothing new after a full fresh pass across all nine checks, including a clean traceability audit. The design is ready for `/implement`.

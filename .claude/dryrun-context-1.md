# Context Dry-Run Report #1

**Reviewed**: 2026-07-04
**Focus**: `C:/Projects/second-brain/CLAUDE.md` (fresh project-context file) — the file-organization / numbering convention + spec-driven section.

**Method**: V self-review (inline) + an independent reviewer sub-agent. The independent pass caught a real contradiction the inline review missed — recorded honestly below.

---

## Critical (found → FIXED)

**[C1] Dryrun files wrongly swept under the "don't number" rule.**
- **Found**: The doc said "do NOT number files inside a spec folder … `dryrun-*.md` by exact name." But the global spec convention numbers dryrun files by review iteration (`dryrun-design-1.md`, `dryrun-design-2.md`). A fresh agent would guess wrong — `dryrun-design.md` (literal) vs `dryrun-design-1.md` (global rule).
- **Root**: two distinct numbering schemes got blurred — the **order-prefix** (`001-`, for research files + spec folders) and the **iteration-suffix** (`-N`, for dryrun review files).
- **Fix applied**: CLAUDE.md now separates the two schemes explicitly and adds dryrun placement (design/code/plan inside the spec folder; context-dryruns at `.claude/` root).

## Warnings (addressed)

- **Research artifact scope** — clarified as ".md and any generated exports (.pdf, etc.)" intent; the paired-number rule stands.
- **Dryrun-context placement** — now stated (`.claude/` root).

## Observations

- Task `_{requirement}_` back-reference (global spec contract) not restated locally — inherited from the global convention, left out to avoid duplication.
- "Current specs" inventory lists only `001-agent-core/` — kept as a live index, updated as specs are added.

---

## Summary

| Critical | Warnings | Observations |
|----------|----------|--------------|
| 1 (fixed) | 2 (addressed) | 2 (noted) |

**Verdict**: PASS **after fix**. Inline self-review initially passed it; the independent reviewer caught the dryrun-numbering contradiction, which is now resolved. (Lesson: self-review is not a substitute for an independent pass — same theme as today's velocity/drift work.)

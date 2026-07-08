# Second Brain

A fresh-built, **evolving agentic system** — a real agent (persona, memory, self-correction, a multi-provider consortium), not a persona-mimic. Built by studying the best of existing agentic systems (OpenClaw, Hermes, Claude Code, and Kaushik's own Velasari / CM / Velhari), then **rebuilding clean under our own principles — reuse the knowledge, not the code.**

Cross-cutting principles: token efficiency, optimum work allocation, local-first, controllability-by-construction.

---

## File organization

Planning and research artifacts live under `.claude/` (`research/`, `specs/`, `plans/`).

### Numbering convention — order-by-prefix

Things that form a sequence carry a zero-padded numeric prefix (`001-`, `002-`, …) by **creation order**, so it's always clear what came before what:

- **Research files** (`.claude/research/`): `NNN-descriptive-name.md`. Keep paired artifacts (the `.md` and any generated `.pdf`) under the **same** number.
- **Spec folders** (`.claude/specs/`): `NNN-feature-name/`.
- **Plan files** (`.claude/plans/`): `NNN-subject-roadmap.md` — a **cross-spec roadmap** (a build plan spanning multiple components/specs, each with its own milestones). A plan bound to a *single* spec's lifecycle stays *inside* that spec folder instead (as its `task.md`).

**Do NOT apply the order-prefix (`001-`) to files *inside* a spec folder** — the folder's own prefix already carries cross-feature order, and the SDLC skills (`/design`, `/implement`, `/dryrun-*`) look up `requirement.md`, `design.md`, `task.md` by **exact name**, so prefixing them breaks the tooling.

Two numbering schemes, don't confuse them:
- **Order-prefix** `NNN-` (`001-`, `002-`) — applies to **research files**, **spec folders**, and **plan files**. Cross-item creation order.
- **Iteration-suffix** `-N` — applies to **dryrun review files** per the global spec convention: `dryrun-design-1.md`, `dryrun-design-2.md`, `dryrun-code-1.md`, `dryrun-context-1.md`. That `N` is a *review-iteration counter*, not the order-prefix.

**Dryrun placement**: `dryrun-design/code/plan-N.md` live *inside* their spec folder; `dryrun-context-N.md` (reviews of `CLAUDE.md` / blueprints) live at `.claude/` root.

---

## Spec-driven development

Each feature: `.claude/specs/NNN-feature/` with `requirement.md` → `design.md` → `task.md`; dryrun before build. (APEX e-spec skills.)

Current specs:
- `001-agent-core/` — high-level component requirement for the core agent (9 components + 2 later-phase).

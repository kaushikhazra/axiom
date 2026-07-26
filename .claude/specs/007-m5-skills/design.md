# M5 · Skills — Design

**Spec:** `007-m5-skills`
**Milestone:** M5 — "agentskills.io progressive disclosure; self-authoring"
**Status:** DRAFT
**Inputs:** `requirement.md` (this spec); `001-agent-core/architecture.md` (Skills as a loop-level port, in the same list as Memory); `006-m4-tools/design.md` (D1 — Tools is adapter-side, the pattern this design deliberately does *not* repeat); installed source read directly — `src/axiom/interfaces.py`, `src/axiom/loop.py`, `src/axiom/providers/base.py`, `src/axiom/agent.py`, `src/axiom/tools/*` (all on `feature/m5-skills`, branched from `feature/agentcore-skeleton`); live spec fetch of `agentskills.io/specification` (2026-07-26, recorded in `requirement.md`).

---

## 1. Overview

M5 adds `axiom.skills` — a **loop-level port** (unlike Tools, which M4 deliberately kept adapter-side). The core mechanism is a **fourth intent kind**, `USE_SKILL`, alongside the existing `RESPOND` / `ACT` / `FINISH`. This is the load-bearing design choice of the whole milestone, so it gets its own section (§2) before anything else.

Everything downstream follows from that one choice:
- Both adapters already share one `reason()` → `_parse_intent()` → loop-dispatch pipeline (`base.py`, confirmed by reading the file — `INTENT_FORMAT_INSTRUCTIONS` and `_parse_intent` are shared, provider-independent). A new intent kind therefore works identically on `ClaudeAdapter` and `LocalAdapter` with **zero adapter-specific code** — no per-provider wiring, unlike M4's Tools gate which needed two different mechanisms (`PreToolUse` hook for KIND-B, direct `ToolRegistry` calls for KIND-A).
- It sidesteps a real conflict M4 already flagged: M4's own Non-Goals rule out an Axiom MCP server exposing `read_file`/`write_file` to Claude ("no Axiom MCP server exposing these to Claude"). If skill *activation* were modeled as a Tool call, KIND-B would have no way to reach it (Claude only sees its own native tools). Modeling activation as a loop-level intent avoids that asymmetry entirely.
- Self-authoring (SK-4) needs **no new mechanism at all** — it is a plain `write_file` (KIND-A) / `Write` (KIND-B) call during an ordinary `ACT`, already gated by M4's existing `GuardrailsGate`. The only Skills-specific behavior is that the *next* Perceive picks up the new file (§4).

---

## Decisions Log

| # | Decision | Rationale |
|---|----------|-----------|
| D1 | Skills is a loop-level port (`loop.py` and `interfaces.py` import from `axiom.skills`), the mirror image of M4's D1 ("Tools is adapter-side"). | Matches `architecture.md`'s port list placement (Skills alongside Memory, not alongside Tools) and SK-1's AC that `loop.py`'s Perceiver call-point consumes `SkillsPort` directly. |
| D2 | Skill activation is a **new `IntentKind.USE_SKILL`** / `UseSkillIntent(skill_name: str)`, parsed by the same shared `_parse_intent()` both adapters already use — not a Tool, not a provider-specific mechanism. | Resolves SK-3's open mechanism question. Reuses the one pipeline both adapters already share instead of building two (KIND-A tool wrapper + some KIND-B equivalent that doesn't actually exist, per M4's MCP Non-Goal). Provider-symmetric by construction. |
| D3 | The discovery catalog (`run_state.skills_catalog`) is refreshed **every Perceive call**, not once per user turn (contrast with `memory_context`, assembled once per turn in `_run_async`). | SK-4's behavioral AC requires an authored skill to appear "on the immediately following cycle" — mid-run, after an `ACT` that wrote a new `SKILL.md`. A once-per-turn snapshot (like memory) would miss it until the next user message. |
| D4 | Activated skill bodies accumulate in `run_state.active_skills: list[SkillContent]` and persist for the rest of the run; they are never evicted mid-run. | SK-3 AC: "available for the remainder of the run... the Conductor does not need to re-request it every cycle." No eviction policy is in scope for M5 (see Future Work) — a run's `max_cycles=10` bound keeps worst-case context growth small. |
| D5 | An unknown `skill_name` in a `UseSkillIntent` (hallucinated by the Conductor) does not crash the loop. `SkillsRegistry.get_skill()` raises `SkillNotFoundError`; `loop.py` catches it and feeds an error observation into `run_state.history` (the same channel `ACT` results already use), then continues the loop. | Consistency with the project-wide "never crash on a bad model output" posture already established by M4 (`ToolResult` never raises, D9) and by `base.py`'s intent-parse retry/fallback path. A hallucinated skill name is a normal, expected failure mode — not exceptional. |
| D6 | `UseSkillIntent` handling counts toward `run_state.cycle_count` (via `observe()`), exactly like `ActIntent`. | Prevents a pathological loop where the Conductor repeatedly emits `USE_SKILL` without making progress — the existing `MAX_CYCLES` bound (10) already guards `ActIntent`; extending the same counter to `UseSkillIntent` costs nothing new and closes an otherwise-open runaway path. |
| D7 | Self-authoring (SK-4) adds **no new tool, no new gate**. The agent writes `{skills_dir}/{name}/SKILL.md` via the existing `write_file` (KIND-A, `DESTRUCTIVE`, `ToolRegistry`) or `Write` (KIND-B, `DESTRUCTIVE`, native SDK tool gated by the existing `PreToolUse` hook) during a normal `ACT` cycle. | Matches `requirement.md`'s Purpose section and M4's own Non-Goal note ("M5 builds on top of M4's registry"). DRY — a second write path or a Skills-specific approval gate would duplicate M4's `GuardrailsGate` for no behavioral difference (`write_file`/`Write` are already `DESTRUCTIVE` and already gated). |
| D8 | `SkillsRegistry` is filesystem-backed and framework-free: it reads `{skills_dir}/*/SKILL.md` with `pathlib` + a hand-rolled YAML-frontmatter split (regex on the leading `---`/`---` block) — no new dependency (no `python-frontmatter`, no `pyyaml`) is added for M5. | The frontmatter is small and flat (5 known keys, `metadata` being the only nested one). A regex split + `yaml.safe_load` on just the frontmatter block would need a `pyyaml` dependency the project doesn't currently have (checked: not in `pyproject.toml`); a minimal hand-rolled line-based parser avoids adding one for a genuinely small parsing job. If skill authors start hand-writing complex nested `metadata`, this is the first thing to revisit (Future Work). |
| D9 | `SkillsPort.search()` (SK-5) is implemented but **not** wired into the loop's per-cycle catalog assembly — `list_skills()` (unfiltered) remains what `loop.py` calls at each Perceive. | Matches `requirement.md` SK-5's own AC: "M5 does not mandate wiring an unconditional-search-instead-of-list-all policy into Perceive." `search()` exists as a `SkillsPort` capability for a future Router-level policy decision, not consumed internally yet. |
| D10 | `skills_dir` is threaded through `Agent.__init__` exactly like M4's `working_dir` — a constructor parameter, no CLI flag added in M5 (same "trivial-or-deferred" posture M4 took). | Consistency (SK-6's own rationale) — no new decision needed, just following the established pattern. |

---

## 2. Intent System Extension

`src/axiom/interfaces.py` — additive changes only (no existing dataclass or Protocol signature changes).

```python
class IntentKind(Enum):
    RESPOND = auto()
    ACT = auto()
    FINISH = auto()
    USE_SKILL = auto()  # M5: activate a skill by name


@dataclass(frozen=True)
class UseSkillIntent:
    skill_name: str = ""
    kind: IntentKind = field(init=False, default=IntentKind.USE_SKILL)


Intent = Union[RespondIntent, ActIntent, FinishIntent, UseSkillIntent]
```

`RunState` gains two M5 fields, following the exact pattern `memory_context` already established (typed as `object`/loosely to avoid a hard import from `axiom.skills` into `interfaces.py` — actually here a direct import is fine and preferred: `axiom.skills.port` has zero dependencies of its own, so no circular-import risk the way `axiom.memory.models` had. Typed precisely, not duck-typed):

```python
from axiom.skills.port import SkillContent, SkillSpec

@dataclass
class RunState:
    user_input: str
    history: list[str]
    cycle_count: int = 0
    spawn_count: int = 0
    memory_context: object = None
    skills_catalog: list[SkillSpec] = field(default_factory=list)   # M5: refreshed every Perceive (D3)
    active_skills: list[SkillContent] = field(default_factory=list)  # M5: accumulates for the run (D4)
```

---

## 3. Skills Port Contract

`src/axiom/skills/port.py` — mirrors `axiom/tools/port.py`'s shape (`ToolSpec`/`ToolResult`/`ToolsPort`) for consistency, adapted to Skills' loop-level role.

```python
"""
Skills port contract -- the loop-level seam for Axiom's self-authored,
progressively-disclosed capabilities.

Unlike ToolsPort (adapter-side, axiom.tools), SkillsPort is consumed
directly by loop.py and interfaces.py -- the same relationship MemoryPort
already has with the core loop (architecture.md places Skills alongside
Memory in the 6-port list, not alongside Tools).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True)
class SkillSpec:
    """Discovery-level payload -- name + description only (agentskills.io
    'discovery' stage). No body, no bundled-file contents."""
    name: str
    description: str


@dataclass(frozen=True)
class SkillContent:
    """Activation-level payload -- the full parsed SKILL.md."""
    name: str
    description: str
    body: str  # Markdown content after the frontmatter block
    frontmatter: dict = field(default_factory=dict)  # optional fields, unenforced (license/compatibility/metadata/allowed-tools)


class SkillNotFoundError(Exception):
    """Raised by get_skill() when skill_name is not in the current catalog.
    Caught by loop.py (D5) -- never propagates past the loop."""


class SkillsPort(Protocol):
    def list_skills(self) -> list[SkillSpec]:
        """Discovery-level catalog of every valid skill. Never raises --
        a malformed skill is excluded and logged, not an error (SK-2)."""
        ...

    def get_skill(self, name: str) -> SkillContent:
        """Full content of one skill. Raises SkillNotFoundError if name
        is not present (or is present but invalid -- same exclusion as
        list_skills(), SK-2)."""
        ...

    def search(self, query: str) -> list[SkillSpec]:
        """Discovery-level results relevant to query (name/description
        keyword match). Not wired into loop.py's catalog assembly in M5
        (D9) -- a capability for future callers."""
        ...
```

---

## 4. SkillsRegistry — the concrete `SkillsPort`

`src/axiom/skills/parser.py` — validation + frontmatter/body split (SK-2), isolated from the registry so it's independently unit-testable.

```python
"""
SKILL.md parsing and validation against the agentskills.io frontmatter
rules (agentskills.io/specification, fetched 2026-07-26 -- see
requirement.md SK-2 for the verbatim rule list).
"""

from __future__ import annotations

import re
from pathlib import Path

from axiom.skills.port import SkillContent

_FRONTMATTER_RE = re.compile(r"\A---\n(.*?)\n---\n(.*)\Z", re.DOTALL)
_NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")  # no leading/trailing/consecutive hyphens


class SkillValidationError(Exception):
    """Raised by parse_skill_md() on any frontmatter/format violation.
    Caught exclusively by SkillsRegistry -- never propagates to loop.py."""


def _parse_frontmatter_block(block: str) -> dict:
    """Minimal line-based key: value parser (D8) -- sufficient for the flat
    5-key frontmatter agentskills.io defines. Only 'metadata' nests; nested
    keys are collected as a flat dict under 'metadata' by indentation."""
    result: dict = {}
    current_key: str | None = None
    for line in block.splitlines():
        if not line.strip():
            continue
        if line.startswith(("  ", "\t")) and current_key == "metadata":
            k, _, v = line.strip().partition(":")
            result.setdefault("metadata", {})[k.strip()] = v.strip().strip('"')
            continue
        k, sep, v = line.partition(":")
        if not sep:
            continue
        current_key = k.strip()
        result[current_key] = v.strip().strip('"')
    return result


def parse_skill_md(path: Path) -> SkillContent:
    """Parse and validate one SKILL.md. path is the file itself
    ({skills_dir}/{name}/SKILL.md); the skill name is derived from the
    PARENT directory name, then cross-checked against frontmatter 'name'
    (spec rule: name must match the parent directory name)."""
    dir_name = path.parent.name
    text = path.read_text(encoding="utf-8")

    m = _FRONTMATTER_RE.match(text)
    if not m:
        raise SkillValidationError(f"{path}: missing or malformed frontmatter block")

    frontmatter = _parse_frontmatter_block(m.group(1))
    body = m.group(2)

    name = frontmatter.get("name", "")
    description = frontmatter.get("description", "")

    if not name:
        raise SkillValidationError(f"{path}: 'name' is required")
    if len(name) > 64 or not _NAME_RE.match(name):
        raise SkillValidationError(
            f"{path}: 'name' {name!r} must be 1-64 chars, lowercase "
            "alphanumeric + hyphens, no leading/trailing/consecutive hyphens"
        )
    if name != dir_name:
        raise SkillValidationError(
            f"{path}: 'name' {name!r} must match parent directory name {dir_name!r}"
        )
    if not description:
        raise SkillValidationError(f"{path}: 'description' is required")
    if len(description) > 1024:
        raise SkillValidationError(f"{path}: 'description' exceeds 1024 chars")

    return SkillContent(name=name, description=description, body=body, frontmatter=frontmatter)
```

`src/axiom/skills/registry.py`

```python
"""
SkillsRegistry -- the concrete SkillsPort. Owns skills_dir; discovers,
validates, and serves skills from {skills_dir}/*/SKILL.md.
"""

from __future__ import annotations

import logging
from pathlib import Path

from axiom.skills.parser import SkillValidationError, parse_skill_md
from axiom.skills.port import SkillContent, SkillNotFoundError, SkillSpec

logger = logging.getLogger("axiom.skills")


class SkillsRegistry:
    def __init__(self, skills_dir: Path) -> None:
        self._skills_dir = skills_dir

    def _discover(self) -> dict[str, SkillContent]:
        """Re-scan skills_dir on every call (D3 -- no caching, so a skill
        authored mid-run is picked up on the very next call). skills_dir
        not existing is a valid, common state (SK-6) -- empty result, not
        an error."""
        found: dict[str, SkillContent] = {}
        if not self._skills_dir.is_dir():
            return found
        for entry in sorted(self._skills_dir.iterdir()):
            skill_md = entry / "SKILL.md"
            if not entry.is_dir() or not skill_md.is_file():
                continue
            try:
                content = parse_skill_md(skill_md)
            except SkillValidationError as exc:
                logger.debug("[SKILL_INVALID] %s", exc)
                continue
            found[content.name] = content
        return found

    def list_skills(self) -> list[SkillSpec]:
        return [
            SkillSpec(name=c.name, description=c.description)
            for c in self._discover().values()
        ]

    def get_skill(self, name: str) -> SkillContent:
        found = self._discover()
        if name not in found:
            raise SkillNotFoundError(f"no such skill: {name!r}")
        return found[name]

    def search(self, query: str) -> list[SkillSpec]:
        q = query.lower()
        return [
            SkillSpec(name=c.name, description=c.description)
            for c in self._discover().values()
            if q in c.name.lower() or q in c.description.lower()
        ]
```

---

## 5. Loop wiring

`src/axiom/loop.py` — additive changes to `PraoLoop.__init__` and `_run_async`.

```python
def __init__(
    self,
    perceive: PerceivePort,
    reason: ReasonPort,
    act: ActPort,
    observe: ObservePort,
    memory: MemoryPort,
    skills: SkillsPort,          # M5: required, no default -- same
                                  # fail-loud posture M4 used for gate/working_dir
    max_cycles: int = MAX_CYCLES,
) -> None:
    ...
    self._skills = skills
```

Inside `_run_async`'s `while True:` loop, immediately before each Perceive call (D3 — refreshed every cycle, not once per turn):

```python
while True:
    run_state.skills_catalog = await asyncio.to_thread(self._skills.list_skills)

    with _maybe_record("perceive", run_id, provider_kind):
        context = await asyncio.to_thread(self._perceive.perceive, run_state)

    with _maybe_record("reason", run_id, provider_kind):
        run_state.spawn_count += 1
        intent = await asyncio.to_thread(self._reason.reason, context)

    if isinstance(intent, RespondIntent):
        ...  # unchanged
    if isinstance(intent, FinishIntent):
        ...  # unchanged

    if isinstance(intent, UseSkillIntent):
        with _maybe_record("act", run_id, provider_kind):  # reuses the Act
            run_state.spawn_count += 1                      # span/counter --
            try:                                             # activation is
                content = await asyncio.to_thread(            # a bounded,
                    self._skills.get_skill, intent.skill_name  # observable
                )                                              # step, same
                run_state.active_skills.append(content)        # shape as ACT
                result = f"[SKILL ACTIVATED] {intent.skill_name}"
            except SkillNotFoundError as exc:
                result = f"[SKILL ERROR] {exc}"

        with _maybe_record("observe", run_id, provider_kind):
            run_state = await asyncio.to_thread(self._observe.observe, result, run_state)

        if run_state.cycle_count >= self._max_cycles:
            raise MaxCyclesExceededError(...)
        continue

    # intent == ACT — unchanged from here
```

No changes to `MemoryPort` handling, `ObservePort`, or the `RespondIntent`/`FinishIntent` branches. `SkillsPort` import added alongside the existing `MemoryPort` import at the top of `loop.py`.

---

## 6. Wire format and parsing (`base.py`)

`INTENT_FORMAT_INSTRUCTIONS` gains a fourth choice, inserted alongside the existing three (exact wording deferred to implementation, shape fixed here):

```
  {"intent": "RESPOND", "text": "<your response to the user>"}
  {"intent": "ACT", "instruction": "<one bounded instruction for the executor>"}
  {"intent": "USE_SKILL", "skill_name": "<name of a skill from AVAILABLE SKILLS>"}
  {"intent": "FINISH"}
```

with an added rule:

```
- "USE_SKILL" requires a "skill_name" field (string) that MUST exactly match a
  name from the [AVAILABLE SKILLS] catalog below. Use it when a skill's
  description indicates it is relevant to the current request, BEFORE
  attempting the task from general knowledge or via ACT. If no available
  skill's description matches, do not guess a name — proceed with RESPOND or
  ACT instead.
```

`_parse_intent()` (module-level, shared) gains one branch:

```python
if intent_str == "USE_SKILL":
    name = data.get("skill_name")
    if not isinstance(name, str) or not name:
        return None, f"USE_SKILL missing or invalid 'skill_name' field: {data!r}"
    return UseSkillIntent(skill_name=name), None
```

`PraoAdapterBase.perceive()` (shared, provider-independent) gains two rendering blocks, inserted after the existing `[PERSONA]` section and before `[CURRENT REQUEST]` (ordering: catalog is background context like memory, so it sits with the other context sections, not at the end next to the format instructions):

```python
if run_state.skills_catalog:
    lines = [f"  - {s.name}: {s.description}" for s in run_state.skills_catalog]
    sections.append("[AVAILABLE SKILLS]\n" + "\n".join(lines))

for skill in run_state.active_skills:
    sections.append(f"[ACTIVE SKILL: {skill.name}]\n{skill.body}")
```

Empty catalog / no active skills → both blocks are simply omitted (list is falsy), matching the existing pattern for `cognitive`/`working` memory sections and `run_state.history`.

---

## 7. Composition root (`agent.py`)

```python
def __init__(
    self,
    ...,
    working_dir: str | Path | None = None,
    skills_dir: str | Path | None = None,   # M5
    auto_approve_tools: bool = False,
) -> None:
    ...
    resolved_working_dir = Path(working_dir) if working_dir is not None else Path.cwd()
    resolved_skills_dir = (
        Path(skills_dir) if skills_dir is not None else resolved_working_dir / "skills"
    )
    ...
    from axiom.skills.registry import SkillsRegistry  # noqa: PLC0415
    skills_registry = SkillsRegistry(skills_dir=resolved_skills_dir)

    self._loop = PraoLoop(
        perceive=adapter,
        reason=adapter,
        act=adapter,
        observe=adapter,
        max_cycles=10,
        memory=self._memory_adapter,
        skills=skills_registry,
    )
```

No new CLI flag (D10) — `skills_dir` is constructor-only in M5, same posture M4 took with `working_dir` before deciding a `--working-dir` flag was trivial-or-deferred.

---

## 8. Self-authoring path (SK-4) — no new code beyond what's already listed

Worth stating explicitly since it's a full user story with no dedicated implementation section: authoring happens through the **existing, unmodified** M4 `write_file` (KIND-A) / `Write` (KIND-B) machinery during a normal `ActIntent` cycle. The Conductor decides to write `{skills_dir}/{new-skill-name}/SKILL.md` the same way it would decide to write any other file; `GuardrailsGate` classifies and gates it exactly as `DESTRUCTIVE` today. The only M5-specific behavior is `SkillsRegistry._discover()` re-scanning `skills_dir` on the *next* call (D3) — which happens automatically, every cycle, per §5. Nothing in `axiom/tools/` changes for M5.

---

## Error Handling

| Failure | Behavior |
|---|---|
| `skills_dir` does not exist | `list_skills()` returns `[]`, `search()` returns `[]` — not an error (SK-6). |
| A `SKILL.md` fails frontmatter validation (SK-2) | Excluded from `list_skills()`/`search()`/`get_skill()`; logged at DEBUG (`[SKILL_INVALID]`) with the specific violation. Does not affect sibling skills. |
| Conductor emits `USE_SKILL` with an unrecognized `skill_name` | `SkillNotFoundError` caught in `loop.py` (D5); a `[SKILL ERROR] ...` string is fed back through the existing `observe()` → history channel; the loop continues (no crash, no run abort). |
| `USE_SKILL` intent JSON missing `skill_name` | `_parse_intent()` returns `(None, error)`, which triggers the *existing* parse-failure retry-then-fallback path already used for any malformed intent (`base.py`, unchanged). |
| Two skills with the same `name` in different directories | Not possible under SK-2's rule (frontmatter `name` must match its own parent directory name, and directory names are unique on a filesystem) — no dedup logic needed. |

---

## Files Changed

| File | Change | AC Trace |
|------|--------|----------|
| `src/axiom/skills/port.py` | New. `SkillSpec`, `SkillContent`, `SkillNotFoundError`, `SkillsPort` Protocol. | SK-1 |
| `src/axiom/skills/parser.py` | New. `parse_skill_md()`, `SkillValidationError`, agentskills.io frontmatter validation. | SK-2 |
| `src/axiom/skills/registry.py` | New. `SkillsRegistry(SkillsPort)` — filesystem discovery, validation exclusion, search. | SK-1, SK-2, SK-5, SK-6 |
| `src/axiom/interfaces.py` | Add `IntentKind.USE_SKILL`, `UseSkillIntent`, extend `Intent` union; add `RunState.skills_catalog` / `RunState.active_skills`. | SK-3 |
| `src/axiom/loop.py` | `PraoLoop.__init__` takes `skills: SkillsPort`; `_run_async` refreshes `skills_catalog` every cycle and handles `UseSkillIntent`. | SK-1, SK-3, SK-4 |
| `src/axiom/providers/base.py` | Extend `INTENT_FORMAT_INSTRUCTIONS` with `USE_SKILL`; extend `_parse_intent()`; extend `perceive()` to render `skills_catalog`/`active_skills`. | SK-3 |
| `src/axiom/agent.py` | Add `skills_dir` constructor parameter (defaults to `{working_dir}/skills`); construct `SkillsRegistry`; pass into `PraoLoop`. | SK-6 |
| `tests/test_skills_parser.py` | New. Frontmatter validation — valid/invalid `name`, missing `description`, length limits, dir-name mismatch. | SK-2 |
| `tests/test_skills_registry.py` | New. Discovery, exclusion of invalid skills, `get_skill()` / `SkillNotFoundError`, `search()`, empty-`skills_dir` case. | SK-1, SK-2, SK-5, SK-6 |
| `tests/test_loop.py` | Extend. `UseSkillIntent` branch — successful activation appends to `active_skills` + history marker; unknown-skill path appends error marker and does not crash; `skills_catalog` refresh timing (per-cycle, not per-turn). | SK-3, SK-4 |
| Existing `PraoLoop(...)` construction call sites (tests + `agent.py`) | Updated to pass `skills=` — breaking-change ripple, same shape as M4's D11 for `LocalAdapter`. Grep `PraoLoop(` across the tree before implementation to enumerate exact sites. | SK-1 |

---

## Future Work (Out of Scope)

- **Semantic/embedding-based `search()`** (SK-5 Out of Scope) — current implementation is keyword substring match; embeddings are a plausible future refinement once real skill volume exists.
- **Active-skill eviction policy** — D4 accumulates without bound within a run; `max_cycles=10` keeps worst case small today, but a longer-running loop in a later milestone may need an eviction/LRU policy.
- **`allowed-tools` frontmatter enforcement** — parsed and stored in `SkillContent.frontmatter` but not wired into `GuardrailsGate` (per `requirement.md` Out of Scope; the field is marked experimental upstream too).
- **`scripts/` execution** — bundled skill scripts are part of the on-disk format (not rejected by validation) but M5 builds no mechanism to execute them.
- **`--skills-dir` CLI flag** — deferred with the same posture M4 used for `--working-dir` (D10).
- **Router-level catalog filtering using `search()`** — D9 leaves `search()` unconsumed internally; a future Router policy (M6+) could use it to bound `skills_catalog` size for large skill collections.

"""
Shared base for all PRAO adapters.

Provides provider-independent perceive() and observe() implementations, the
shared INTENT_FORMAT_INSTRUCTIONS wire-format constant, and the _parse_intent()
helper used by every adapter's reason() method.

Import boundary: axiom.interfaces only — zero SDK imports.
"""

from __future__ import annotations

import json
import logging
import re

from axiom.interfaces import (
    ActIntent,
    FinishIntent,
    Intent,
    RespondIntent,
    RunState,
)

logger = logging.getLogger("axiom.providers")

# ---------------------------------------------------------------------------
# Intent format instructions — injected verbatim into every reason() prompt
# (§4.1 wire format). Moved from claude_adapter.py so both adapters share the
# identical string — single source of truth.
# ---------------------------------------------------------------------------

INTENT_FORMAT_INSTRUCTIONS: str = """\
---
RESPONSE FORMAT INSTRUCTIONS (mandatory):
Reply with EXACTLY ONE JSON object on a single line. No markdown. No code fences.
No explanation before or after. Only the JSON object.

Choose ONE of:
  {"intent": "RESPOND", "text": "<your response to the user>"}
  {"intent": "ACT", "instruction": "<one bounded instruction for the executor>"}
  {"intent": "FINISH"}

Rules:
- "intent" must be exactly "RESPOND", "ACT", or "FINISH" (case-sensitive).
- "RESPOND" requires a "text" field (string). Use ONLY for requests answerable from
  the conversation context or established general knowledge — no tools needed.
- "ACT" requires an "instruction" field (string). You MUST use ACT (never RESPOND)
  whenever the request requires: web search, real-time or current data, file access,
  running commands, or any side effect. Do NOT attempt to answer such requests from
  memory or training data — you have zero tools; route to ACT so the executor can act.
- STALENESS RULE: Your training knowledge may be months or years out of date. For ANY
  fact that changes over time — software/library versions, prices, who currently holds
  a role or record, news, standings, or anything phrased "latest / current / newest /
  today / now / as of" — assume your stored answer is OUTDATED and route to ACT, even
  if you feel certain. Do not answer time-varying questions from memory.
- TOOL-LESS-MEANS-DELEGATE: You (the reasoning step) have NO tools by design. This does
  not mean you cannot get live data — an executor with web search, bash, and file access
  runs whatever instruction you return in an ACT. NEVER refuse or answer directly because
  you "lack a tool"; instead route to ACT and the executor will use its tools.
- "FINISH" has no additional fields. Use it only when the task is fully complete with no response needed.
- The entire response must be parseable as a single JSON object.

Examples:
  User: "What's the capital of France?"
  → {"intent": "RESPOND", "text": "Paris."} (stable fact, no tool needed)

  User: "What's the latest stable Python version?"
  → {"intent": "ACT", "instruction": "Search the web for the latest stable Python release version."} (time-varying; stored version is likely stale)

  User: "What files are in this directory?"
  → {"intent": "ACT", "instruction": "List the files in the current directory."} (requires a tool)
---"""


# ---------------------------------------------------------------------------
# _parse_intent — shared intent parser (module-level; used by all adapters)
# ---------------------------------------------------------------------------


def _extract_json_from_text(text: str) -> str | None:
    """Attempt to extract a JSON object substring from loosely-formatted text.

    Handles common weak-model failure modes:
    1. JSON wrapped in markdown code fences — single OR multiple fences.
    2. JSON embedded in surrounding explanation text (finds first { ... }).

    Uses re.finditer with a non-greedy inter-fence pattern so that each code
    fence is matched individually (avoiding the multi-fence greedy-span bug where
    .*  with DOTALL spans from the first ``` to the last ```, swallowing the
    delimiters in between and producing un-parseable JSON).  Within each block,
    greedy \\{.*\\} is used so nested JSON objects are captured in full.

    Returns the first candidate that json.loads() into a dict, or None.
    The caller (json.loads in _parse_intent) re-validates the returned string.
    """
    candidates: list[str] = []

    # Strategy 1: find ALL fenced blocks individually.
    # Non-greedy .*? between ``` markers prevents spanning multiple fences;
    # greedy \{.*\} within each block captures nested JSON in full.
    for m in re.finditer(r"```(?:\w+)?\s*(.*?)\s*```", text, re.DOTALL):
        block = m.group(1).strip()
        brace_m = re.search(r"\{.*\}", block, re.DOTALL)
        if brace_m:
            candidates.append(brace_m.group(0).strip())

    # Strategy 2: bare {…} anywhere in the full text (greedy, handles nested braces)
    brace_m = re.search(r"\{.*\}", text, re.DOTALL)
    if brace_m:
        candidates.append(brace_m.group(0).strip())

    # Return the first candidate that successfully parses as a JSON dict.
    # strict=False: weak local models embed literal newlines inside JSON string
    # values (e.g. RESPOND text with "\n"). Standard json.loads rejects these as
    # invalid control characters; strict=False accepts them without altering the
    # parsed value. The candidate string is returned unchanged for the caller's
    # final json.loads call (which also uses strict=False).
    for candidate in candidates:
        try:
            if isinstance(json.loads(candidate, strict=False), dict):
                return candidate
        except (json.JSONDecodeError, ValueError):
            continue

    return None


def _parse_intent(raw: str) -> tuple[Intent | None, str | None]:
    """Parse a raw model response string into an Intent dataclass.

    Implements the §4.1 + §6 parse rules with enhanced pre-processing for
    weak local models (strip code fences, extract first {…} if direct parse fails).

    Parse order:
      1. Strip leading/trailing whitespace.
      2. Attempt direct json.loads() — happy path (Claude-quality output, clean JSON).
      3. On failure: attempt to extract a JSON candidate via _extract_json_from_text()
         and retry json.loads() — handles weak-model wrapping in prose/fences.
      4. Validate intent field and required per-type fields.

    Returns:
        (intent, None) on success.
        (None, error_message) on any parse or validation failure.
    """
    text = raw.strip()

    # Step 1: Direct parse attempt (happy path — does not alter ClaudeAdapter behaviour)
    # strict=False: tolerate literal control characters (e.g. \n) inside JSON string
    # values, which weak local models sometimes emit in RESPOND text fields.
    data: object = None
    last_exc: str | None = None
    try:
        data = json.loads(text, strict=False)
    except (json.JSONDecodeError, ValueError) as exc:
        last_exc = str(exc)

    # Step 2: Enhanced pre-processing for weak models (additive; skipped on clean JSON)
    if data is None:
        extracted = _extract_json_from_text(text)
        if extracted is not None:
            try:
                data = json.loads(extracted, strict=False)
            except (json.JSONDecodeError, ValueError) as exc:
                last_exc = str(exc)

    if data is None:
        return None, last_exc or f"no valid JSON found in: {text!r}"

    # Step 3: Field validation
    if not isinstance(data, dict):
        return None, f"expected JSON object, got {type(data).__name__}"

    intent_str = data.get("intent")

    if intent_str == "RESPOND":
        t = data.get("text")
        if not isinstance(t, str):
            return None, f"RESPOND missing or invalid 'text' field: {data!r}"
        return RespondIntent(text=t), None

    if intent_str == "ACT":
        instr = data.get("instruction")
        if not isinstance(instr, str):
            return None, f"ACT missing or invalid 'instruction' field: {data!r}"
        return ActIntent(instruction=instr), None

    if intent_str == "FINISH":
        return FinishIntent(), None

    return None, f"unknown intent value: {intent_str!r}"


# ---------------------------------------------------------------------------
# PraoAdapterBase — shared base class for all PRAO adapters
# ---------------------------------------------------------------------------


class PraoAdapterBase:
    """Shared base for all PRAO adapters.

    Provides provider-independent perceive() and observe() implementations.
    Subclasses must implement reason() and act() (provider-specific).

    The Protocols in interfaces.py are the contracts; PraoAdapterBase is an
    adapter-side implementation convenience — it does NOT appear in interfaces.py
    and is not part of the public contract.
    """

    def __init__(self, persona: str) -> None:
        self._persona = persona

    # ------------------------------------------------------------------
    # PerceivePort implementation
    # ------------------------------------------------------------------

    def perceive(self, run_state: RunState) -> str:
        """Assemble the reasoning context prompt.

        M3: When run_state.memory_context is set (AssembledContext), renders both
        memory tiers into the prompt per design §4.4:
          - cognitive_memories → "[ADDITIONAL CONTEXT FROM MEMORY]" section (system-prompt slot)
          - working_context   → "[PREVIOUS CONVERSATIONS]" section (history slot)
        Memory owns the substance; the loop sets run_state.memory_context and this
        method renders it — no memory imports here (duck-typed via attribute access).
        """
        sections: list[str] = []
        sections.append(f"[PERSONA]\n{self._persona}")

        # M3 B1 fix: render assembled memory context into the prompt so the model
        # reasons over recalled knowledge and prior conversation turns.
        ctx = run_state.memory_context
        if ctx is not None:
            cognitive = getattr(ctx, "cognitive_memories", None) or []
            working = getattr(ctx, "working_context", None) or []

            if cognitive:
                lines = []
                for m in cognitive:
                    mem_type = getattr(m, "memory_type", "memory")
                    content = getattr(m, "content", str(m))
                    lines.append(f"  [{mem_type}] {content}")
                sections.append("[ADDITIONAL CONTEXT FROM MEMORY]\n" + "\n".join(lines))

            if working:
                conv_lines = []
                for unit in working:
                    u_text = getattr(unit, "user_text", "")
                    a_text = getattr(unit, "agent_text", "")
                    conv_lines.append(f"  User: {u_text}\n  Agent: {a_text}")
                sections.append("[PREVIOUS CONVERSATIONS]\n" + "\n\n".join(conv_lines))

        if run_state.history:
            history_lines = [
                f"Step {i + 1}: {result}" for i, result in enumerate(run_state.history)
            ]
            sections.append(
                "[TOOL EXECUTION RESULTS — read these carefully]\n"
                + "\n".join(history_lines)
                + "\n\n[NOTE: The above are REAL outputs from tool executions. "
                "The task has been partially or fully completed. "
                "You now have the data you need. "
                "Use RESPOND to deliver the answer to the user — do NOT request another ACT unless there is clearly something missing.]"
            )

        sections.append(f"[CURRENT REQUEST]\n{run_state.user_input}")
        sections.append(INTENT_FORMAT_INSTRUCTIONS)

        return "\n\n".join(sections)

    # ------------------------------------------------------------------
    # ObservePort implementation
    # ------------------------------------------------------------------

    def observe(self, result: str, run_state: RunState) -> RunState:
        """Capture act() result and update run-state — identical to M1 §7.4.

        Mutate-and-return semantics: appends result to history, increments
        cycle_count, returns the same RunState object. No behavioural change.
        """
        run_state.history.append(result)
        run_state.cycle_count += 1
        return run_state

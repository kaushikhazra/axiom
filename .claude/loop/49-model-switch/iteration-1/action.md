# Action

**Cycle 1 writes no production code.** The artifact exists and is green; this cycle records
the baseline and settles the two shape questions that decide everything after it.

## 1. Record the baseline

- `env AXIOM_HOST=http://127.0.0.1:1 AXIOM_MODEL=nonsense:99b AXIOM_DEBUG_MAX_CONTEXT=7 uv run pytest -q`
  Expect **377 passed**. Record it; it is the floor.
- Copy the golden transcript to `.tmp/transcript-baseline-49.txt`.
- `gh issue view 49` and record all 34 criteria as `not-started`.

## 2. Write out what a switch changes and what it must not

Before touching `_chat`, list its locals and mark each **rebound** or **untouched**. This is
most of AC 10 to AC 17 and is cheaper to get right on paper than in a debugger:

`model`, `capable`, `declarations`, `callable_names`, `effective_context`, `chat_options`,
`messages`, `limits`, `attached`, `instructions`, `running_usage`.

`running_usage` is the interesting one and is not named in any criterion: it is the last
turn's real token count and it drives compaction. It came from a **different model's**
tokenizer. Decide what happens to it on a switch, record the decision and the reasoning, and
do not leave it to whatever the code happens to do.

## 3. Settle the two shape questions

- **Where `/model` is handled.** The loop reads a line, then checks `EXIT_COMMANDS`. A switch
  has to happen before the line becomes a message, and it must rebind locals in `_chat` -
  which a helper function cannot do by returning one value. Decide the shape: a small
  dataclass holding the six rebindable things, a nested function, or handling it inline.
  **Prefer whatever keeps `_chat` readable**, and say why in the log.
- **Whether the switch reuses `_settle_model`.** It is close but not identical: no fatal exits,
  Ctrl-C means cancel rather than leave, and the marked entry is the *current* model rather
  than the remembered one. Decide reuse-with-parameters against a sibling function, and record
  the reasoning. A copy is the wrong answer - AC 2 requires the two lists to agree.

## 4. Probe one thing live

Against the local Ollama: start a session on `qwen2.5:7b` **with tools**, and confirm by hand
what a conversation containing a tool call looks like in `messages`. AC 11 turns on those
messages surviving a switch to `gemma2:2b`, which cannot call tools, and the exact shape of
what has to survive is worth seeing once rather than assuming.

## 5. Write cycle 2's action

Cycle 2 implements. Say which criteria it takes and in what order. Suggested, by dependency:

- The command and its two forms first, reusing `models.picked` and `terminal.show_models`.
- Then the rebinding - the six locals - and the announcement.
- Then remembering, which is `_remember` unchanged.
- Then the fit-check for the carried conversation, which is mostly letting the existing
  compaction see the new window.
- The transcript last, once the output has stopped moving.

## Record

Status for all 34. The locals table. The two shape decisions with their reasoning. The
`running_usage` decision. The baseline count.

**Write no questions into anything.** Decide, record the decision and the reasoning under a
heading that says so, carry on. The exception is safety, not uncertainty.

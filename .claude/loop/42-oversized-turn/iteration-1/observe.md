# Observe

Record each cycle:

- A status token for **every one of #42's 8 criteria**: `not-started` / `attempted` /
  `met-with-evidence` / `blocked`. All eight get a token every cycle, even "no change."
  Cite them as "AC 4".
- How far that moved from the last cycle, and what moved it.
- What is still missing, and whether it can be closed from here at all.
- Any assumption that changed.

## What counts as evidence

- **AC 3 and AC 4 need a real session driven into the refusal and back out.** They are claims
  about a session continuing, which a single-call unit test cannot make. `AXIOM_DEBUG_MAX_CONTEXT`
  is the tool and the reproduction is one line: set it to 200 and type anything.
- **AC 1, 2, 7 and 8 may be settled with stubs.** They are about what the code does with a
  history it is handed.
- **AC 5 and AC 6 are about wording, and wording is the easiest thing to fake.** A test that
  the message contains "conversation" proves a string was built. What the criterion asks is
  whether the message names *what is actually too large* - which means a test has to set up
  both cases and check the message differs between them.

## The trap this issue sits on

#41 added a system prompt to every request. It is a **fixed** cost - the user cannot shorten
it by typing less, and compaction cannot forget it, because it is deliberately held outside
`messages` where compaction never sees it.

That is what makes AC 4 reachable: *"A session cannot reach a state where every message,
however short, is refused."* With a small enough context the prompt alone exceeds it, and
today every turn is refused with advice to try a shorter message - advice that cannot work.

So a fix that only compacts harder does not meet AC 4. **Something has to give when the
non-negotiable part alone will not fit**, and saying plainly that the session cannot continue
(AC 6) is a legitimate answer where pretending a shorter message would help is not.

## Where this will be tempting to cheat

**AC 1 - "whatever the previous turn's reported usage was".** Compaction triggers today on
`running_usage` from the last completed turn. On the first turn of a session that is `None`,
so compaction never runs and the size check refuses immediately. The criterion is that the
size check itself can cause compaction, independently of usage. Do not satisfy it by lowering
the usage threshold.

**AC 2 - "refused only once compaction has already run".** Ordering, not wording. A refusal
that happens before compaction has been given its chance fails this however well it is
phrased.

**AC 7 - "no extra compaction, no extra output".** The golden transcript is the instrument.
A turn that fits must produce byte-identical output.

**AC 8 - "the same way compaction triggered by usage does".** #32 spent three cycles making
compaction report what it let go. A second compaction path that forgets silently would pass a
size assertion and destroy that.

## Standing checks

- **The full suite is re-run in every cycle that changes code**, and the result recorded.
  The baseline is **255 tests, green** at scaffold time.
- **The suite must stay green with no Ollama and no network**, and must not be changeable by
  the environment:
  `env AXIOM_HOST=http://127.0.0.1:1 AXIOM_MODEL=nonsense:99b AXIOM_DEBUG_MAX_CONTEXT=7 uv run pytest -q`
- **The golden transcript is the behaviour record**, and AC 7 is measured by it. Copy it
  aside in cycle 1.
- **Before regenerating the transcript, run `diff` and read all of it.** #41 cycle 2
  regenerated off pytest's assertion summary, which reports the *first* differing index and
  reads like it reports the whole difference. It was 100 lines and two compaction scenarios
  were destroyed. Restored, but the lesson is cheap to reuse and expensive to relearn.
- **A stub that contradicts the thing under test proves nothing.** #40 found `given_page`
  announcing `text/plain` over HTML; #41 found `StubClient` reporting `prompt_eval_count=1`
  whatever it was sent. Both had passed for two issues. When a test here stubs usage or size,
  check it is not asserting against a number it invented.
- If a criterion cannot be met as written, say so plainly and say why. #35 replaced one on
  evidence, #32 amended three, #40 and #41 each had one broken by the cold read. That is an
  acceptable outcome; quietly reinterpreting one is not.

## The cycle that writes the code never declares it done

A separate cycle checks, reading the criteria from GitHub **before** the diff and before the
previous log. **Attack each criterion rather than confirming it.** This has now caught a real
defect twice running - #40's AC 7 and #41's AC 9 - each after the implementing cycle had
written `met-with-evidence` beside it. Both were found by a hostile input, neither by
rereading code.

## Goal check

- **Met** - all 8 criteria `met-with-evidence`, the recovery ones from a real session driven
  into the refusal and out again, suite green and hermetic, transcript accounted for.
- **Not met** - report which criteria moved and which did not, and write the next action.
- **Answer did not move** - report the flat result and stop. Do not run another variant.

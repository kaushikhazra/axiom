"""Does a real model reach for a skill instead of answering from memory?

AC 15 and AC 16. These cannot be stubbed and they cannot be asserted: the
question is about a model's judgement, and the only honest answer is a count.

**Excluded from the default run** by the `live` marker in `pyproject.toml`.
They need Ollama, they take minutes, and a suite that quietly acquires a
network dependency makes every wall-clock reading in this loop meaningless.

    uv run pytest -m live -s

**Nothing here executes a tool call.** The measurement is whether the model
*asks* for `invoke_skill`, and the call is counted and dropped. No file is
written, no command is run, and the model is never asked for destructive work -
CLAUDE.md's rule for testing tools before security exists.
"""

import pytest

from axiom import skills, tools
from axiom.backend import Call, OllamaBackend, call_from_text

pytestmark = pytest.mark.live

HOST = "http://localhost:11434"

# Ten is the minimum that separates "usually" from "once". Fewer would let a
# single lucky run stand as evidence, which is the failure AC 16 names.
RUNS = 10

# The skill covers something a model cannot already know - a project's own
# release steps - so a model that does not invoke it has to answer from memory
# and will be visibly making something up. That contrast is the measurement; a
# skill about a general topic would let a correct-looking answer hide a miss.
SKILL = """---
name: release-checklist
description: The steps this project takes before cutting a release
---

Before a release, in order:

1. Run the full suite and record the wall-clock time.
2. Regenerate the golden baseline and read its diff.
3. Tag the commit as `release/<version>`.
"""

ASKED = "What do I need to do before cutting a release here?"


@pytest.fixture(scope="module")
def catalogue(tmp_path_factory):
    directory = tmp_path_factory.mktemp("skills")
    made = directory / "release-checklist"
    made.mkdir()
    (made / "SKILL.md").write_text(SKILL, encoding="utf-8")
    return skills.read(directory)


def _declarations() -> list[dict]:
    """Every tool, as a session with one skill loaded would declare them."""
    return tools.declarations()


def _asked_for_the_skill(model: str, catalogue) -> bool:  # noqa: ANN001
    """One run. True if the model called `invoke_skill`.

    The call is counted and dropped - never executed. What is being measured is
    the reaching, not the following.
    """
    backend = OllamaBackend(HOST)
    messages = [
        {
            "role": "system",
            "content": tools.system_prompt(
                tools.Limits(), skills.catalogue_text(catalogue)
            ),
        },
        {"role": "user", "content": ASKED},
    ]
    reply = ""
    for piece in backend.stream(model, messages, tools=_declarations()):
        if isinstance(piece, Call):
            if piece.name == "invoke_skill":
                return True
        else:
            reply += piece.text

    # A call the model announced as text rather than as a structured call. #34
    # exists for exactly this and the session already handles it, so a
    # measurement that only counted structured calls would be measuring below
    # the seam - and would score a model zero for asking correctly in the other
    # shape. qwen2.5-coder does this; the first version of this test scored it
    # 0/10 for it.
    announced = call_from_text(reply, {tool.name for tool in tools.REGISTRY.values()})
    return announced is not None and announced.name == "invoke_skill"


def test_each_installed_model_reaches_for_a_skill_that_fits(catalogue, capsys):
    """AC 15 and AC 16 - a count per model, and the bad ones written down.

    This does not assert a threshold. A model that scores badly is AC 16's case
    and the criterion is met by recording the number, not by reaching one. The
    assertion is only that the measurement happened for every installed model.
    """
    backend = OllamaBackend(HOST)
    installed = backend.installed()
    results: dict[str, str] = {}

    for model in installed:
        if not backend.supports_tools(model):
            # Cannot call any tool, so cannot invoke a skill. AC 16's case, and
            # recorded as what it is rather than as a score of zero - zero
            # implies it tried.
            results[model] = "no tool support"
            continue
        hits = sum(_asked_for_the_skill(model, catalogue) for _ in range(RUNS))
        results[model] = f"{hits}/{RUNS}"

    with capsys.disabled():
        print("\n\nAC 15 - invoked the skill instead of answering from memory")
        for model, score in results.items():
            print(f"  {model:<20} {score}")

    assert len(results) == len(installed), "a model was installed and not measured"

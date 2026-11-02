"""Memory that outlives a session (#95), through Synaptra.

Synaptra is a separate program that stores and recalls; axiom's MCP client talks to
it like any other server. What this module adds is everything around that: where it
lives, setting it up the first time, and the three places where leaving it to the
model alone was measured to fail.

**Why its own venv, inside the project.** Synaptra 2.1.1 requires `mcp<2.0`, axiom
requires `mcp>=2.1.1` and does `from mcp import Client`, which 1.30 does not have. A
dry-run install of one into the other's environment replaced mcp 2.1.1 with 1.30.0 and
would have broken every MCP server axiom starts, not only this one. So Synaptra gets a
venv of its own, and the data sits beside it. The owner's call, 2026-11-02: project
local, and axiom outside it. Release blocker: Synaptra moves to mcp 2.x before any
axiom release (recorded on #95).

**Where the model alone failed**, measured 2026-11-02 on gemma4:e2b against the real
server:

- `memory_store` needs a `rater`, the model left it out, Synaptra refused, and the
  model then told the user it had remembered. `prepared` supplies the rater and
  `outcome` makes a refusal read as one.
- Nothing makes a small model recall before it answers. `recalled` asks for it.
"""

import json
import re
import shutil
import subprocess
import sys
import time
from collections.abc import Callable
from pathlib import Path

from . import servers
from .config import ServerSpec

SERVER = "synaptra"
STORE = "memory_store"
RECALL = "memory_recall"
# Only these two are offered to the model. Of Synaptra's eighteen tools the other
# sixteen are curation and graph work a chat does not need, and the descriptions of
# all eighteen cost about 3000 tokens on every request.
OFFERED = (STORE, RECALL)
STORE_CALL = servers.qualified(SERVER, STORE)
RECALL_CALL = servers.qualified(SERVER, RECALL)

# Relative to where axiom was started, like `.axiom/mcp.json` and the rest of
# `.axiom/`. Resolved when used, never frozen at setup: a project folder that is
# renamed still finds its memory.
DEFAULT_DIRECTORY = Path(".axiom") / "memory"

SYNAPTRA = "synaptra==2.1.1"
EMBEDDING_MODEL = "all-MiniLM-L6-v2"
# Synaptra needs 3.11 or later; 3.12 is what its dependencies are built for. axiom
# itself may run on a newer interpreter that torch has no wheel for.
PYTHON = "3.12"
# Approximate, and said to be: measured on Windows with the CPU build of torch,
# 2026-11-02 (a venv of 875 MB; a model cache of 175 MB; 136 s on a good line).
# Other platforms differ, and torch's default build elsewhere is much larger.
PACKAGES_MB = 875
MODEL_MB = 175

# The first start loads the embedding model before it answers: 19 to 25 s measured
# warm, more when the model has to be read from a cold disk.
START_TIMEOUT = 120.0

SOURCE_PREFIX = "axiom:"

RECALL_LIMIT = 3
PROGRESS_EVERY = 1.0  # seconds between progress lines of the same download

# Run through the venv's own interpreter rather than the `synaptra` console script,
# because pip writes the venv's absolute path into that script. A project folder that
# is renamed would leave a launcher that points at the old name.
LAUNCH = "from synaptra.server import main; main()"

PROMPT = (
    "You have a memory that lasts across sessions. When the user asks you to remember "
    f"something, call {STORE_CALL} with the fact as `content`, and say you remembered "
    "it only when the result begins with 'stored'. If the result begins with 'error', "
    "tell the user it was not remembered. Anything recalled for the current question "
    "is given to you in a system note; use it only when it bears on what was asked."
)

Progress = Callable[[str], None]


class Memory:
    """One project's memory: where it lives and whether it is ready."""

    def __init__(self, directory: Path | str | None = None) -> None:
        self.directory = Path(directory) if directory else DEFAULT_DIRECTORY
        self.venv = self.directory / "venv"
        self.data = self.directory / "data"
        # Written last. A venv without it is half-installed, whatever else is in it.
        self.ready = self.directory / "ready"

    @property
    def python(self) -> Path:
        scripts = self.venv / ("Scripts" if sys.platform == "win32" else "bin")
        return scripts / ("python.exe" if sys.platform == "win32" else "python")

    def is_ready(self) -> bool:
        return self.ready.is_file() and self.python.is_file()

    def spec(self) -> ServerSpec:
        """How axiom starts Synaptra from this project's venv.

        `--transport stdio`, with the store under the project. `SYNAPTRA_DB` is
        absolute because the server is a separate process that does not share axiom's
        working directory.
        """
        return ServerSpec(
            SERVER,
            command=str(self.python.resolve()),
            args=("-c", LAUNCH, "--transport", "stdio"),
            env={
                "SYNAPTRA_BACKEND": "surrealkv-file",
                "SYNAPTRA_DB": str(self.data.resolve()),
            },
            tools=OFFERED,
            start_timeout=START_TIMEOUT,
        )

    def ensure(
        self,
        say: Progress,
        install: "Callable[[Memory, Progress], str | None] | None" = None,
    ) -> str | None:
        """Make it ready, or say why it could not be. None means ready.

        The first run in a project sets it up and says what it is fetching (#95
        AC 1). A run after that does nothing here (AC 2). A setup that cannot finish
        returns its reason and is tried again next run (AC 3), which is why nothing is
        recorded until the last step: `ready` is the only evidence that counts.

        `install` is a parameter so a test can hand in a script this repo owns. A
        test never fetches a package or a model (CLAUDE.md, #43).
        """
        if self.is_ready():
            return None
        for line in (
            "memory: first run in this project. Setting it up here, once:",
            f"  Synaptra and its packages, about {PACKAGES_MB} MB, into {self.venv}",
            f"  the embedding model {EMBEDDING_MODEL}, about {MODEL_MB} MB, "
            "from huggingface.co into your Hugging Face cache",
            f"  this needs the network once; memories stay in {self.data}",
        ):
            say(line)
        return (install or install_for_real)(self, say)


def install_for_real(memory: Memory, say: Progress) -> str | None:
    """Create the venv, install Synaptra, fetch the model, then mark it ready."""
    try:
        # Whatever a quit or a failure left behind: a venv with no `ready` beside it
        # is half-installed and is rebuilt from nothing (#95 AC 9). Only the venv; the
        # data directory holds memories and is never touched.
        if memory.venv.exists():
            shutil.rmtree(memory.venv)
        memory.directory.mkdir(parents=True, exist_ok=True)
        python = str(memory.python)
        uv = shutil.which("uv")
        if uv:
            steps = [
                [uv, "venv", "--python", PYTHON, str(memory.venv)],
                [uv, "pip", "install", "--python", python, SYNAPTRA],
            ]
        else:
            steps = [
                [sys.executable, "-m", "venv", str(memory.venv)],
                [python, "-m", "pip", "install", SYNAPTRA],
            ]
        steps.append(
            [
                python,
                "-c",
                "from sentence_transformers import SentenceTransformer as S; "
                f"S({EMBEDDING_MODEL!r})",
            ]
        )
        for command in steps:
            failure = _run(command, say)
            if failure:
                return failure
        memory.ready.write_text(
            json.dumps({"synaptra": SYNAPTRA, "model": EMBEDDING_MODEL}) + "\n",
            encoding="utf-8",
        )
    except OSError as failed:
        return _one_line(str(failed))
    return None


def _run(command: list[str], say: Progress) -> str | None:
    """One setup step, its output passed on, or a one-line reason it failed."""
    last = ""
    shown = 0.0
    process = subprocess.Popen(  # noqa: S603
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    try:
        for raw in process.stdout:
            line = raw.strip()
            if not line:
                continue
            last = line
            # A download redraws one line many times a second. Passed on as it
            # came it would scroll thousands of rows, so a line that looks like a
            # progress bar waits its turn.
            bar = "%" in line or "|" in line
            now = time.monotonic()
            if bar and now - shown < PROGRESS_EVERY:
                continue
            shown = now
            say(f"  {line}")
        process.wait()
    finally:
        # A quit during the download lands here too (#95 AC 9): the child must not
        # outlive axiom still writing into a folder the next run will remove.
        if process.poll() is None:
            process.kill()
            process.wait()
    if process.returncode:
        return _one_line(last or f"{Path(command[0]).name} exited {process.returncode}")
    return None


def described(failure: str) -> str:
    """A server-start failure, in memory's words when it is memory's (#95 AC 4).

    `Servers` records a server that did not start as `<name>: <reason>`, which for
    Synaptra would read as a tool the user never heard of. The user knows it as
    memory, and a missing memory is not a missing tool.
    """
    prefix = f"{SERVER}: "
    if failure.startswith(prefix):
        return f"memory: unavailable - {failure.removeprefix(prefix)}"
    return failure


def _one_line(text: str) -> str:
    return text.splitlines()[0][:200] if text else "unknown reason"


# -- the three places the model alone failed --------------------------------------


def prepared(name: str, arguments: dict, model: str) -> dict:
    """A server tool's arguments, with what Synaptra insists on filled in.

    `rater` is the model that is storing. Synaptra scores importance relative to the
    rater, so a store with none is refused outright (measured). The model is not
    asked for it because a small model does not reliably supply what the schema
    marks optional but the server requires.
    """
    if name != STORE_CALL:
        return arguments
    # Always the model's own name, never what the model wrote: measured live on
    # 2026-11-02, gemma4:e2b filled `rater` with "axiom" when it could, which is not
    # a model and cannot be compared with any other score.
    #
    # And `source` as well, because the rater alone is not kept: measured live, a store
    # with a rater and no importance is recorded as `auto:heuristic`, and the model's
    # name appears nowhere in the memory. `source` is a field the server keeps as given,
    # so it is where the model's name survives (#95 AC 11).
    return {**arguments, "rater": model, "source": f"{SOURCE_PREFIX}{model}"}


def outcome(name: str, result: str) -> str:
    """What a server's tool result means for the model, said plainly.

    A refused store is rewritten so that it cannot be read as success. On
    2026-11-02 gemma4:e2b was told Synaptra had refused its store and answered "I
    have remembered that": the refusal was JSON in a field the model did not weigh.
    Axiom cannot write the model's reply, but it can make the result unambiguous
    and show the user the same words (#95 AC 13).
    """
    if name != STORE_CALL:
        return result
    try:
        document = json.loads(result)
    except ValueError:
        document = None
    if isinstance(document, dict) and document.get("success") is True:
        stored = (document.get("data") or {}).get("content") or ""
        return f"stored: {_one_line(str(stored))}"
    if isinstance(document, dict):
        reason = _one_line(str(document.get("error") or "no reason given"))
    else:
        reason = _one_line(result.removeprefix("error:").strip())
    return (
        f"error: NOT stored. {reason}. Tell the user this was not remembered; "
        "do not say it was."
    )


def relevant(memory: dict) -> bool:
    """Whether a recalled memory is worth putting in front of the model.

    Synaptra returns up to `limit` memories whatever the question, and its score does
    not separate a near match from the nearest of a bad lot: measured against a real
    store on 2026-11-02, "what is my cat called?" and "what is the weather in London"
    both returned the cat memory at exactly the same score (0.0213). What it does say
    is which strategies found each one, and the keyword strategy is the only one that
    means the memory shares a word with the question.

    **A judgement, not a measurement**, and an interim one. It errs towards saying
    nothing (#95 AC 16), which costs a missed recall on a pure paraphrase. The real
    fix is a similarity from Synaptra, which belongs to its maintainer; see #95.
    """
    return "keyword" in set(memory.get("found_by") or ())


# Words that are in nearly every question and so say nothing about which memory it is
# about. Looking each up would fetch whatever a stored sentence happens to contain.
STOPWORDS = frozenset(
    "a an the is are was were be am do does did i me my mine you your we our it its "
    "he she they them what which who whom whose when where why how and or but of in "
    "on at to for with from by about as into than that this these those there have "
    "has had not no can could would should will just so if then any some tell "
    "please remember".split()
)
# How many words of one question are looked up. Each is a round trip that embeds the
# word, so this bounds what recall adds to a turn.
MAX_WORDS = 6


def question_words(text: str) -> list[str]:
    """The words of a question worth looking up, in order, once each."""
    words: list[str] = []
    for word in re.findall(r"\w+", text.lower()):
        if word not in STOPWORDS and word not in words:
            words.append(word)
    return words[:MAX_WORDS]


def recall_for(ask: Callable[[dict], str], text: str) -> tuple[list[str], str | None]:
    """What memory holds that shares a word with this question, and why not if it failed.

    **One lookup per word, not one for the sentence.** Measured live (2026-11-02):
    Synaptra's keyword search matched "cat" and "Biscuit" and never "what is my cat
    called?", which found the same memory by meaning alone. A sentence therefore
    carries no keyword signal, and a word does. `ask` takes the recall arguments and
    returns the server's raw answer.
    """
    texts: list[str] = []
    for word in question_words(text):
        found, why = recalled(ask({"query": word, "limit": RECALL_LIMIT}))
        if why:
            return [], why
        texts.extend(item for item in found if item not in texts)
    return texts[:RECALL_LIMIT], None


def recalled(result: str) -> tuple[list[str], str | None]:
    """The memories worth showing, and why recall failed if it did.

    Never raises: a store that cannot answer costs the turn its memory, not the turn.
    """
    try:
        document = json.loads(result)
    except ValueError:
        return [], _one_line(result.removeprefix("error:").strip())
    if not isinstance(document, dict) or not document.get("success"):
        reason = document.get("error") if isinstance(document, dict) else None
        return [], _one_line(str(reason or "recall failed"))
    found = (document.get("data") or {}).get("memories") or []
    texts = [
        str(item.get("content") or "").strip()
        for item in found
        if isinstance(item, dict) and relevant(item)
    ]
    return [text for text in texts if text][:RECALL_LIMIT], None


def note_for(texts: list[str]) -> dict | None:
    """What goes in front of the model for this turn, or None when nothing does.

    A system message beside the conversation rather than inside it: it is true of
    this question only, and kept in the history it would be recalled again and again
    until compaction swallowed it. Nothing when nothing was recalled (#95 AC 14).
    """
    if not texts:
        return None
    lines = "\n".join(f"- {text}" for text in texts)
    return {
        "role": "system",
        "content": f"From the user's earlier sessions (your memory):\n{lines}",
    }

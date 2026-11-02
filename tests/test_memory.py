"""#95: memory across sessions, through Synaptra.

No test here fetches a package or a model, or starts the real Synaptra. Where a real
process is needed it is `tests/fake_synaptra.py` - ours, started with the interpreter
running the suite - which answers in the shapes the real server was measured to answer
in. What these tests cannot say is whether the real server's ranking is any good, or
whether a small model stores when asked: those rows are driven live, see the cycle logs.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

import axiom
from axiom import backend, config, memory, servers
from axiom.backend import Call
from axiom.config import ServerSpec
from conftest import StubBackend, feed

HERE = Path(__file__).parent


# --- where it lives, and whether it is ready ----------------------------------


def make_ready(found: memory.Memory) -> None:
    found.python.parent.mkdir(parents=True)
    found.python.write_text("", encoding="utf-8")
    found.ready.write_text("{}", encoding="utf-8")


def test_ready_needs_both_the_marker_and_the_interpreter(tmp_path):
    """AC 9, the half that can be shown without a process: `ready` is the evidence."""
    found = memory.Memory(tmp_path / "m")
    assert not found.is_ready()

    found.python.parent.mkdir(parents=True)
    found.python.write_text("", encoding="utf-8")
    assert not found.is_ready(), "an interpreter without the marker is half-installed"

    found.python.unlink()
    found.ready.write_text("{}", encoding="utf-8")
    assert not found.is_ready(), "a marker without the interpreter is not usable"


def test_the_default_directory_is_inside_the_project(monkeypatch):
    """AC 6, AC 7: under `.axiom/`, beside mcp.json, relative to where axiom started."""
    monkeypatch.undo()  # the autouse isolation points it at a temp directory
    assert not memory.DEFAULT_DIRECTORY.is_absolute()
    assert memory.DEFAULT_DIRECTORY.parts[0] == ".axiom"


def test_the_server_is_launched_from_the_projects_own_venv(tmp_path):
    """AC 6, AC 15, AC 17: its interpreter, its data, two tools, and a long first start."""
    found = memory.Memory(tmp_path / "m")
    spec = found.spec()

    assert Path(spec.command) == found.python.resolve()
    assert str(tmp_path) in spec.command
    # Not the console script: pip writes the venv's absolute path into that.
    assert spec.args[0] == "-c" and "synaptra.server" in spec.args[1]
    assert spec.args[2:] == ("--transport", "stdio")
    assert Path(spec.env["SYNAPTRA_DB"]) == found.data.resolve()
    assert Path(spec.env["SYNAPTRA_DB"]).is_absolute()
    assert spec.tools == (memory.STORE, memory.RECALL)
    assert spec.start_timeout == memory.START_TIMEOUT > config.DEFAULT_MCP_START_TIMEOUT


def test_a_server_may_carry_its_own_start_bound():
    attached = servers.Servers(
        (ServerSpec("a"), ServerSpec("b", start_timeout=90.0)), start_timeout=30.0
    )
    assert attached._bound(attached.specs[0]) == 30.0
    assert attached._bound(attached.specs[1]) == 90.0


# --- the first run (AC 1, AC 2, AC 3) ----------------------------------------


def test_the_first_run_says_what_it_fetches_before_it_fetches_it(tmp_path):
    """AC 1: what, how large, and where it goes - said before the installer runs."""
    found = memory.Memory(tmp_path / "m")
    said: list[str] = []
    order: list[str] = []

    def install(target, say):  # noqa: ANN001
        order.append("installed")
        say("downloading")

    def record(line):  # noqa: ANN001
        order.append("said")
        said.append(line)

    assert found.ensure(record, install=install) is None

    text = "\n".join(said)
    assert "first run" in text
    assert str(memory.PACKAGES_MB) in text and str(memory.MODEL_MB) in text
    assert memory.EMBEDDING_MODEL in text and "huggingface.co" in text
    assert str(found.venv) in text and str(found.data) in text
    assert "network" in text
    assert order.index("installed") > order.index("said")
    assert said[-1] == "downloading", "what the installer says reaches the user"


def test_a_later_run_downloads_and_says_nothing(tmp_path):
    """AC 2."""
    found = memory.Memory(tmp_path / "m")
    make_ready(found)
    said: list[str] = []

    def install(target, say):  # noqa: ANN001
        raise AssertionError("a project that is already set up was set up again")

    assert found.ensure(said.append, install=install) is None
    assert said == []


def test_a_setup_that_cannot_finish_gives_its_reason_and_is_tried_again(tmp_path):
    """AC 3: the reason comes back, nothing is marked ready, the next run retries."""
    found = memory.Memory(tmp_path / "m")
    attempts = []

    def offline(target, say):  # noqa: ANN001
        attempts.append(1)
        return "could not reach pypi.org"

    assert found.ensure(lambda _: None, install=offline) == "could not reach pypi.org"
    assert not found.is_ready()
    assert found.ensure(lambda _: None, install=offline) == "could not reach pypi.org"
    assert len(attempts) == 2


# --- the installer (AC 4, AC 6, AC 9) -----------------------------------------


@pytest.fixture
def steps(monkeypatch):
    """Record the installer's commands instead of running them."""
    recorded: list[list[str]] = []
    monkeypatch.setattr(memory, "_run", lambda command, say: recorded.append(command))
    return recorded


def test_setup_installs_the_pinned_package_into_the_projects_venv(
    tmp_path, steps, monkeypatch
):
    """AC 4, AC 5: a venv of its own, Synaptra pinned, the model fetched, `ready` last."""
    monkeypatch.setattr(memory.shutil, "which", lambda name: "UV")
    found = memory.Memory(tmp_path / "m")

    assert memory.install_for_real(found, lambda _: None) is None

    flat = [" ".join(command) for command in steps]
    assert flat[0].startswith("UV venv") and str(found.venv) in flat[0]
    assert flat[1].startswith("UV pip install") and memory.SYNAPTRA in flat[1]
    assert str(found.python) in flat[1], (
        "installed into the project's venv, not axiom's"
    )
    assert memory.EMBEDDING_MODEL in flat[2]
    assert found.ready.is_file()


def test_setup_falls_back_to_pip_when_there_is_no_uv(tmp_path, steps, monkeypatch):
    monkeypatch.setattr(memory.shutil, "which", lambda name: None)
    found = memory.Memory(tmp_path / "m")

    memory.install_for_real(found, lambda _: None)

    assert steps[0][1:3] == ["-m", "venv"]
    assert steps[1][1:4] == ["-m", "pip", "install"] and memory.SYNAPTRA in steps[1]


def test_a_half_installed_venv_is_rebuilt_and_the_memories_are_not_touched(
    tmp_path, steps, monkeypatch
):
    """AC 9: a venv with no `ready` beside it goes; the data directory never does."""
    monkeypatch.setattr(memory.shutil, "which", lambda name: "UV")
    found = memory.Memory(tmp_path / "m")
    found.python.parent.mkdir(parents=True)
    (found.venv / "leftover").write_text("from a quit", encoding="utf-8")
    found.data.mkdir(parents=True)
    (found.data / "memories").write_text("kept", encoding="utf-8")

    memory.install_for_real(found, lambda _: None)

    assert not (found.venv / "leftover").exists()
    assert (found.data / "memories").read_text(encoding="utf-8") == "kept"


def test_a_step_that_fails_stops_the_setup_and_leaves_no_marker(tmp_path, monkeypatch):
    """AC 3, AC 9."""
    monkeypatch.setattr(memory.shutil, "which", lambda name: "UV")
    seen = []

    def fail_second(command, say):  # noqa: ANN001
        seen.append(command)
        return "no matching distribution" if len(seen) == 2 else None

    monkeypatch.setattr(memory, "_run", fail_second)
    found = memory.Memory(tmp_path / "m")

    assert memory.install_for_real(found, lambda _: None) == "no matching distribution"
    assert len(seen) == 2, "nothing after the failed step ran"
    assert not found.ready.exists()


def test_quitting_during_the_download_leaves_no_marker(tmp_path, monkeypatch):
    """AC 9: Ctrl-C mid-install. Whatever is on disk, `ready` is not, so the next run
    rebuilds."""
    monkeypatch.setattr(memory.shutil, "which", lambda name: "UV")

    def interrupted(command, say):  # noqa: ANN001
        raise KeyboardInterrupt

    monkeypatch.setattr(memory, "_run", interrupted)
    found = memory.Memory(tmp_path / "m")

    with pytest.raises(KeyboardInterrupt):
        memory.install_for_real(found, lambda _: None)
    assert not found.ready.exists()
    assert not found.is_ready()


def test_a_step_streams_its_output_and_reports_a_failure_in_one_line():
    said: list[str] = []
    ok = memory._run([sys.executable, "-c", "print('one'); print('two')"], said.append)
    assert ok is None and said == ["  one", "  two"]

    said.clear()
    failure = memory._run(
        [
            sys.executable,
            "-c",
            "print('resolving'); print('no such package'); raise SystemExit(1)",
        ],
        said.append,
    )
    assert failure == "no such package"


def test_a_redrawn_progress_line_is_not_passed_on_thousands_of_times():
    said: list[str] = []
    script = "for i in range(300): print(f'{i}%|####|')"
    memory._run([sys.executable, "-c", script], said.append)
    assert 0 < len(said) < 20


def test_a_step_that_is_killed_does_not_outlive_the_setup(monkeypatch):
    """AC 9: the child is stopped when the reader is interrupted."""
    process = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(60)"],
        stdout=subprocess.PIPE,
        text=True,
    )

    class Interrupting:
        stdout = iter([])

        def __init__(self):
            self.returncode = None

        def poll(self):
            return process.poll()

        def wait(self):
            raise KeyboardInterrupt

        def kill(self):
            process.kill()

    # Wait raises once, as a Ctrl-C would; the cleanup then kills and waits again.
    stub = Interrupting()
    calls = {"n": 0}

    def wait():
        calls["n"] += 1
        if calls["n"] == 1:
            raise KeyboardInterrupt
        process.wait()

    stub.wait = wait
    monkeypatch.setattr(memory.subprocess, "Popen", lambda *a, **k: stub)
    with pytest.raises(KeyboardInterrupt):
        memory._run(["x"], lambda _: None)
    assert process.poll() is not None, "the child was left running"


# --- where the model alone failed (AC 11, AC 13, AC 14, AC 16) ------------------


def test_a_store_gets_the_name_of_the_model_that_made_it():
    """AC 11. The model is not relied on to supply what the server insists on."""
    given = memory.prepared(memory.STORE_CALL, {"content": "x"}, "qwen2.5:7b")
    assert given == {"content": "x", "rater": "qwen2.5:7b"}

    # Measured live: gemma4:e2b wrote rater="axiom" when it was free to, which is
    # not a model. Whatever the model supplies, the rater is the model's own name.
    named = memory.prepared(
        memory.STORE_CALL, {"content": "x", "rater": "axiom"}, "qwen2.5:7b"
    )
    assert named["rater"] == "qwen2.5:7b"

    other = {"query": "q"}
    assert memory.prepared(memory.RECALL_CALL, other, "qwen2.5:7b") is other


def test_a_stored_memory_is_reported_as_one_short_line():
    """AC 12."""
    result = json.dumps(
        {"success": True, "data": {"id": "1", "content": "cat is Biscuit"}}
    )
    assert memory.outcome(memory.STORE_CALL, result) == "stored: cat is Biscuit"


def test_a_refused_store_cannot_be_read_as_success():
    """AC 13: the words of the real refusal, measured 2026-11-02."""
    refusal = json.dumps(
        {
            "success": False,
            "error": "rater is required when setting importance.",
            "data": None,
        }
    )
    said = memory.outcome(memory.STORE_CALL, refusal)
    assert said.startswith("error:") and "NOT stored" in said
    assert "rater is required" in said
    assert "do not say it was" in said

    assert memory.outcome(
        memory.STORE_CALL, "error: synaptra did not answer"
    ).startswith("error: NOT stored")
    assert memory.outcome(memory.RECALL_CALL, "anything") == "anything"


RECALL = {
    "success": True,
    "data": {
        "memories": [
            {
                "content": "my cat is Biscuit",
                "found_by": ["semantic", "keyword", "temporal"],
            },
            {"content": "closest of a bad lot", "found_by": ["semantic", "temporal"]},
            {"content": "found only by words", "found_by": ["keyword"]},
            {"content": "  ", "found_by": ["semantic", "keyword"]},
        ]
    },
}


def test_only_a_memory_sharing_a_word_with_the_question_is_put_forward():
    """AC 16: Synaptra gives no similarity, so this is a judgement, and says so.

    Found by meaning alone, or by recency, is "the closest thing there was". The score
    does not tell them apart: the real server gave the cat memory 0.0213 for a cat
    question and for a question about the weather in London.
    """
    texts, why = memory.recalled(json.dumps(RECALL))
    assert texts == ["my cat is Biscuit", "found only by words"] and why is None


def test_a_question_is_looked_up_a_content_word_at_a_time():
    """The sentence carries no keyword signal; its words do (measured live)."""
    assert memory.question_words(
        "What is my cat called, and which city do I live in?"
    ) == [
        "cat",
        "called",
        "city",
        "live",
    ]
    assert memory.question_words("the THE cat cat") == ["cat"]
    assert len(memory.question_words(" ".join(f"word{n}" for n in range(30)))) == (
        memory.MAX_WORDS
    )
    assert memory.question_words("what is the") == []


def lookup(store: dict[str, list[str]]):
    """A stand-in for the server that, like the real one, only matches single words."""

    def ask(arguments: dict) -> str:
        found = store.get(arguments["query"], [])
        return json.dumps(
            {
                "success": True,
                "data": {
                    "memories": [
                        {"content": c, "found_by": ["semantic", "keyword"]}
                        for c in found
                    ]
                },
            }
        )

    return ask


def test_each_word_that_hits_contributes_its_memory_once():
    ask = lookup(
        {"cat": ["cat is Biscuit"], "called": ["cat is Biscuit", "x is called y"]}
    )
    texts, why = memory.recall_for(ask, "what is my cat called?")
    assert texts == ["cat is Biscuit", "x is called y"] and why is None


def test_a_question_with_no_content_word_in_memory_recalls_nothing():
    """AC 16."""
    texts, why = memory.recall_for(
        lookup({"cat": ["cat is Biscuit"]}), "weather in London"
    )
    assert texts == [] and why is None
    assert memory.recall_for(lookup({}), "what is it") == ([], None)


def test_the_first_lookup_that_fails_ends_recall_with_its_reason():
    """AC 21."""
    calls = []

    def ask(arguments: dict) -> str:
        calls.append(arguments["query"])
        return "error: synaptra did not answer"

    texts, why = memory.recall_for(ask, "cat called")
    assert texts == [] and "did not answer" in why
    assert calls == ["cat"], "a dead server is asked once, not once per word"


def test_recall_that_found_nothing_gives_the_model_nothing():
    """AC 14, AC 18."""
    empty = json.dumps({"success": True, "data": {"memories": []}})
    texts, why = memory.recalled(empty)
    assert texts == [] and why is None
    assert memory.note_for(texts) is None


def test_a_recall_that_failed_says_why_and_never_raises():
    """AC 21."""
    texts, why = memory.recalled("error: synaptra could not run memory_recall (gone)")
    assert texts == [] and "could not run memory_recall" in why
    texts, why = memory.recalled(
        json.dumps({"success": False, "error": "store unreachable"})
    )
    assert texts == [] and why == "store unreachable"
    assert memory.recalled("not json at all")[0] == []


def test_what_is_recalled_goes_in_as_one_system_note():
    note = memory.note_for(["a", "b"])
    assert note["role"] == "system"
    assert "- a" in note["content"] and "- b" in note["content"]


def test_memory_follows_tools_and_mcp_and_its_own_switch(monkeypatch):
    """AC 5: on with nothing said; there is no switch to turn it on."""
    monkeypatch.delenv("AXIOM_MEMORY")
    assert config.resolve([]).memory_enabled
    assert not config.resolve(["--no-memory"]).memory_enabled
    assert not config.resolve(["--no-mcp"]).memory_enabled
    assert not config.resolve(["--no-tools"]).memory_enabled
    monkeypatch.setenv("AXIOM_MEMORY", "off")
    assert not config.resolve([]).memory_enabled


# --- through a real session, against a server the tests own ----------------------


@pytest.fixture
def live(tmp_path, monkeypatch):
    """Memory switched on and pointed at `tests/fake_synaptra.py`.

    `ensure` and `spec` are replaced, so no setup runs and the server is ours; the
    wiring in `main` and `_chat` is the real thing.
    """
    monkeypatch.delenv("AXIOM_MEMORY")
    monkeypatch.chdir(tmp_path)
    store = tmp_path / "fake-store.json"
    monkeypatch.setenv("FAKE_SYNAPTRA_FILE", str(store))
    monkeypatch.setattr(memory.Memory, "ensure", lambda self, say, install=None: None)
    monkeypatch.setattr(
        memory.Memory,
        "spec",
        lambda self: ServerSpec(
            memory.SERVER,
            command=sys.executable,
            args=(str(HERE / "fake_synaptra.py"),),
            # A server is given exactly the environment its spec names, so the
            # switches a test sets are passed on by name.
            env={
                "FAKE_SYNAPTRA_FILE": str(store),
                **{
                    k: v
                    for k, v in os.environ.items()
                    if k.startswith("FAKE_SYNAPTRA_")
                },
            },
            tools=memory.OFFERED,
        ),
    )
    return store


def system_notes(backend_: StubBackend) -> list[str]:
    return [
        m["content"]
        for sent in backend_.streamed
        for m in sent[1:]
        if m["role"] == "system"
    ]


def store_call(content: str = "my cat is called Biscuit") -> Call:
    return Call(memory.STORE_CALL, {"content": content})


def test_a_fact_told_in_one_session_comes_back_in_the_next(live, capsys, monkeypatch):
    """AC 10 (structure), AC 11, AC 12, AC 19: against a stand-in, not the real thing.

    The real run - a local Ollama model, the real Synaptra, the memory seen in its own
    store - is owed to the live pass and is not claimed here.
    """
    first = StubBackend(turns=[[store_call()], ["Noted."]])
    feed(monkeypatch, ["remember my cat is called Biscuit", "/exit"])
    axiom.main([], using=first)
    told = capsys.readouterr().out
    assert "stored: my cat is called Biscuit" in told
    saved = json.loads(live.read_text(encoding="utf-8"))
    assert saved == [{"content": "my cat is called Biscuit", "rater": "qwen2.5:7b"}]

    second = StubBackend(turns=[["Biscuit."]])
    feed(monkeypatch, ["what is my cat called?", "/exit"])
    axiom.main([], using=second)
    told = capsys.readouterr().out

    notes = system_notes(second)
    assert any("Biscuit" in note for note in notes), (
        "the memory never reached the model"
    )
    assert "memory: 1 from earlier sessions" in told


def test_a_question_that_matches_nothing_adds_nothing(live, capsys, monkeypatch):
    """AC 14, AC 16."""
    live.write_text(json.dumps([{"content": "my cat is called Biscuit", "rater": "m"}]))
    stub = StubBackend()
    feed(monkeypatch, ["what is the weather in London", "/exit"])
    axiom.main([], using=stub)

    assert not any("earlier sessions" in note for note in system_notes(stub))
    assert "from earlier sessions" not in capsys.readouterr().out


def test_an_empty_store_changes_nothing_the_model_sees(live, monkeypatch):
    """AC 18."""
    stub = StubBackend()
    feed(monkeypatch, ["what is my cat called?", "/exit"])
    axiom.main([], using=stub)

    assert not any("earlier sessions" in note for note in system_notes(stub))
    assert stub.streamed, "the turn still ran"


def test_a_note_is_for_one_question_only(live, monkeypatch):
    """AC 14: recalled for this turn, not carried into the history."""
    live.write_text(json.dumps([{"content": "my cat is called Biscuit", "rater": "m"}]))
    stub = StubBackend(turns=[["one"], ["two"]])
    feed(monkeypatch, ["what is my cat called?", "weather in London", "/exit"])
    axiom.main([], using=stub)

    assert any("Biscuit" in note for note in system_notes(stub)[:1])
    assert not any(
        "Biscuit" in m["content"] for m in stub.streamed[1] if m["role"] != "system"
    )
    assert not any("earlier sessions" in m["content"] for m in stub.streamed[1][1:])


def test_the_model_is_offered_store_and_recall_and_nothing_else_of_synaptras(
    live, monkeypatch
):
    """AC 15's counterpart, AC 17."""
    stub = StubBackend()
    feed(monkeypatch, ["hello", "/exit"])
    axiom.main([], using=stub)

    offered = {tool["function"]["name"] for tool in stub.tools_sent[0]}
    assert {memory.STORE_CALL, memory.RECALL_CALL} <= offered
    assert not any("archive" in name for name in offered)


def test_the_prompt_mentions_memory_only_when_memory_answered(live, monkeypatch):
    on = StubBackend()
    feed(monkeypatch, ["hello", "/exit"])
    axiom.main([], using=on)
    assert memory.STORE_CALL in on.streamed[0][0]["content"]


def test_a_refused_store_reaches_the_user_and_the_model_as_a_failure(
    live, capsys, monkeypatch
):
    """AC 13: both halves axiom controls. What the model then writes is its own."""
    monkeypatch.setenv("FAKE_SYNAPTRA_REFUSE", "1")
    stub = StubBackend(turns=[[store_call()], ["I have remembered that."]])
    feed(monkeypatch, ["remember my cat is called Biscuit", "/exit"])
    axiom.main([], using=stub)

    told = capsys.readouterr().out
    assert "NOT stored" in told
    result = [m for m in stub.streamed[1] if m["role"] == "tool"][0]["content"]
    assert result.startswith("error: NOT stored") and "do not say it was" in result


def test_recall_that_fails_is_said_and_the_chat_carries_on(live, capsys, monkeypatch):
    """AC 21, in the form that can be driven: the store answers with a failure."""
    monkeypatch.setenv("FAKE_SYNAPTRA_BREAK", "1")
    stub = StubBackend(turns=[["still here"]])
    feed(monkeypatch, ["hello", "/exit"])
    axiom.main([], using=stub)

    told = capsys.readouterr().out
    assert "memory: unavailable - store unreachable" in told
    assert "still here" in told


def test_axiom_never_stores_a_conversation_by_itself(live, monkeypatch):
    """AC 14: a session in which the model never calls store leaves the store alone.

    Said to the model as plainly as a user could say it, and the model (a stub that only
    answers) does not store. Whatever axiom does around a turn, it must not write.
    """
    stub = StubBackend(turns=[["Noted."], ["Of course."]])
    feed(
        monkeypatch,
        ["remember my cat is called Biscuit", "and my city is Pune", "/exit"],
    )
    axiom.main([], using=stub)

    assert not live.exists(), "something stored without the model asking"


def test_two_projects_keep_separate_memories(tmp_path):
    """AC 20: each project's server is given its own data directory, inside it."""
    here = memory.Memory(tmp_path / "one" / ".axiom" / "memory").spec()
    there = memory.Memory(tmp_path / "two" / ".axiom" / "memory").spec()

    one, two = Path(here.env["SYNAPTRA_DB"]), Path(there.env["SYNAPTRA_DB"])
    assert one != two
    assert (tmp_path / "one") in one.parents and (tmp_path / "two") in two.parents
    assert one not in two.parents and two not in one.parents


def test_a_memory_server_that_will_not_start_is_called_memory(
    tmp_path, monkeypatch, capsys
):
    """AC 4: the user knows it as memory, not as a tool named synaptra."""
    monkeypatch.delenv("AXIOM_MEMORY")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(memory.Memory, "ensure", lambda self, say, install=None: None)
    monkeypatch.setattr(
        memory.Memory,
        "spec",
        lambda self: ServerSpec(
            memory.SERVER,
            command=sys.executable,
            args=("-c", "raise SystemExit(3)"),
            tools=memory.OFFERED,
            start_timeout=10.0,
        ),
    )
    stub = StubBackend(turns=[["a plain reply"]])
    feed(monkeypatch, ["hello", "/exit"])

    axiom.main([], using=stub)

    out = capsys.readouterr()
    assert "memory: unavailable - " in out.err
    assert "synaptra:" not in out.err
    assert "a plain reply" in out.out
    assert memory.STORE_CALL not in stub.streamed[0][0]["content"]


def test_a_failure_that_is_not_memorys_is_left_alone():
    assert memory.described("files: no tool named x") == "files: no tool named x"
    assert memory.described("synaptra: Connection closed").startswith(
        "memory: unavailable"
    )


def test_no_memory_server_outlives_axiom(live, monkeypatch):
    """AC 22: a real process, observed while axiom is running and afterwards."""
    from test_mcp import WatchesChildren, surviving

    stub = WatchesChildren()
    feed(monkeypatch, ["hello", "/exit"])
    axiom.main([], using=stub)

    assert stub.seen, "no memory server was running - the test would prove nothing"
    assert surviving(stub.seen) == []


# --- the run around it (AC 1, AC 3) -------------------------------------------


def test_nothing_is_fetched_for_a_session_that_never_begins(tmp_path, monkeypatch):
    """AC 1: no host, no download. Setup comes after the model is settled."""
    monkeypatch.delenv("AXIOM_MEMORY")
    monkeypatch.chdir(tmp_path)
    called = []
    monkeypatch.setattr(
        memory.Memory, "ensure", lambda self, say, install=None: called.append(1)
    )
    stub = StubBackend(listing=backend.BackendError("unreachable"))

    with pytest.raises(SystemExit):
        axiom.main([], using=stub)
    assert called == []


def test_a_setup_that_failed_leaves_a_plain_chat_and_a_one_line_reason(
    tmp_path, monkeypatch, capsys
):
    """AC 3."""
    monkeypatch.delenv("AXIOM_MEMORY")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        memory.Memory,
        "ensure",
        lambda self, say, install=None: "could not reach pypi.org",
    )
    stub = StubBackend(turns=[["a plain reply"]])
    feed(monkeypatch, ["hello", "/exit"])

    axiom.main([], using=stub)

    out = capsys.readouterr()
    assert "memory: unavailable - could not reach pypi.org" in out.err
    assert "a plain reply" in out.out
    assert memory.STORE_CALL not in stub.streamed[0][0]["content"]


def test_memory_that_is_switched_off_is_never_set_up(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    called = []
    monkeypatch.setattr(
        memory.Memory, "ensure", lambda self, say, install=None: called.append(1)
    )
    feed(monkeypatch, ["hello", "/exit"])
    axiom.main([], using=StubBackend())
    assert called == []

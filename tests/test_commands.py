"""Running commands.

Every command here is harmless - echo, a python one-liner, a sleep. No deletes,
no git, no network, nothing outside tmp_path. The security stories have not
landed, and CLAUDE.md governs what these are allowed to do.
"""

import sys
import time

from axiom import tools

PYTHON = sys.executable


def run(command: str) -> str:
    return tools.run("run_command", {"command": command})


def test_a_command_returns_its_output():
    assert "hello" in run(f"{PYTHON} -c \"print('hello')\"")


def test_any_program_can_be_invoked():
    """AC 14: no fixed list of permitted programs."""
    assert "3" in run(f'{PYTHON} -c "print(1 + 2)"')


def test_there_is_no_allowlist_to_get_past():
    """AC 14, stated so a future allowlist has to delete this test rather than
    quietly appear beside it."""
    source = tools.__file__
    text = open(source, encoding="utf-8").read()
    for forbidden in ("ALLOWED_COMMANDS", "PERMITTED", "allowlist", "whitelist"):
        assert forbidden not in text


def test_standard_error_comes_back_too():
    """AC 15: neither stream is silently discarded."""
    result = run(f"{PYTHON} -c \"import sys; sys.stderr.write('trouble')\"")

    assert "trouble" in result
    assert "stderr" in result, "the user cannot tell which stream it came from"


def test_both_streams_come_back_together():
    result = run(f"{PYTHON} -c \"import sys; print('out'); sys.stderr.write('err')\"")

    assert "out" in result
    assert "err" in result


def test_a_failing_command_is_reported_as_failing():
    """AC 16: never described as success, and the status is named."""
    result = run(f'{PYTHON} -c "import sys; sys.exit(3)"')

    assert "error:" in result
    assert "3" in result


def test_a_failing_command_still_returns_what_it_printed():
    """The output before a failure is often the whole explanation."""
    result = run(f"{PYTHON} -c \"import sys; print('partial work'); sys.exit(1)\"")

    assert "partial work" in result
    assert "error:" in result


def test_a_command_with_no_output_says_so_rather_than_looking_broken():
    """AC 26: silence is not failure."""
    result = run(f'{PYTHON} -c "pass"')

    assert "no output" in result
    assert "error" not in result


def test_a_command_that_will_not_finish_is_stopped(monkeypatch):
    """AC 27: stopped at the limit, and the user told it was stopped."""
    monkeypatch.setattr(tools, "COMMAND_TIMEOUT_SECONDS", 0.5)

    started = time.monotonic()
    result = run(f'{PYTHON} -c "import time; time.sleep(30)"')
    elapsed = time.monotonic() - started

    assert "stopped" in result
    assert elapsed < 10, "waited for the command instead of stopping it"


def test_a_stopped_command_is_actually_killed(monkeypatch, tmp_path):
    """A command reported as stopped must not still be running.

    Telling the user it was stopped while it carries on working is worse than
    not stopping it at all - they believe nothing is happening.
    """
    marker = tmp_path / "survived.txt"
    monkeypatch.setattr(tools, "COMMAND_TIMEOUT_SECONDS", 0.5)

    script = (
        "import time, pathlib; time.sleep(2); "
        f"pathlib.Path(r'{marker}').write_text('still here')"
    )
    result = run(f'{PYTHON} -c "{script}"')

    assert "stopped" in result
    time.sleep(3)  # long enough for the child to have finished, had it survived
    assert not marker.exists(), "the stopped command kept running"


def test_the_working_directory_is_where_commands_run(monkeypatch, tmp_path):
    """AC 32's mechanism. Its default and override are wired to config later."""
    monkeypatch.setattr(tools, "WORKING_DIRECTORY", str(tmp_path))

    result = run(f'{PYTHON} -c "import os; print(os.getcwd())"')

    assert str(tmp_path) in result

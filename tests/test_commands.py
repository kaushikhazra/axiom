"""Running commands.

Every command here is harmless - echo, a python one-liner, a sleep. No deletes,
no git, no network, nothing outside tmp_path. The security stories have not
landed, and CLAUDE.md governs what these are allowed to do.
"""

import subprocess
import sys
import time

import pytest

from axiom import tools

PYTHON = sys.executable


def run(command: str, limits: tools.Limits = tools.DEFAULT_LIMITS) -> str:
    return tools.run("run_command", {"command": command}, limits)


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


def test_a_command_that_will_not_finish_is_stopped():
    """AC 27: stopped at the limit, and the user told it was stopped."""
    started = time.monotonic()
    result = run(
        f'{PYTHON} -c "import time; time.sleep(30)"',
        tools.Limits(command_timeout=0.5),
    )
    elapsed = time.monotonic() - started

    assert "stopped" in result
    assert elapsed < 10, "waited for the command instead of stopping it"


def test_a_stopped_command_is_actually_killed(tmp_path):
    """A command reported as stopped must not still be running.

    Telling the user it was stopped while it carries on working is worse than
    not stopping it at all - they believe nothing is happening.
    """
    marker = tmp_path / "survived.txt"

    script = (
        "import time, pathlib; time.sleep(2); "
        f"pathlib.Path(r'{marker}').write_text('still here')"
    )
    result = run(f'{PYTHON} -c "{script}"', tools.Limits(command_timeout=0.5))

    assert "stopped" in result
    time.sleep(3)  # long enough for the child to have finished, had it survived
    assert not marker.exists(), "the stopped command kept running"


def test_the_working_directory_is_where_commands_run(tmp_path):
    """AC 32's mechanism."""
    result = run(
        f'{PYTHON} -c "import os; print(os.getcwd())"',
        tools.Limits(working_directory=str(tmp_path)),
    )

    assert str(tmp_path) in result


def test_ctrl_c_during_a_command_kills_it(monkeypatch, tmp_path):
    """AC 30: cancelling must stop the work, not just stop watching it.

    A turn that unwinds while the process carries on leaves work happening
    that nobody is waiting for and nobody can see.
    """
    marker = tmp_path / "survived.txt"
    real_communicate = subprocess.Popen.communicate
    seen = []

    def interrupt_the_first_wait(self, *args, **kwargs):
        seen.append(1)
        if len(seen) == 1:
            raise KeyboardInterrupt
        return real_communicate(self, *args, **kwargs)

    monkeypatch.setattr(subprocess.Popen, "communicate", interrupt_the_first_wait)

    script = (
        "import time, pathlib; time.sleep(2); "
        f"pathlib.Path(r'{marker}').write_text('still here')"
    )
    with pytest.raises(KeyboardInterrupt):
        run(f'{PYTHON} -c "{script}"')

    time.sleep(3)
    assert not marker.exists(), "the cancelled command kept running"


def test_a_cancelled_command_does_not_swallow_the_interrupt():
    """The turn has to unwind, or the session does not return to the prompt."""
    real_communicate = subprocess.Popen.communicate
    seen = []

    def interrupt_the_first_wait(self, *args, **kwargs):
        seen.append(1)
        if len(seen) == 1:
            raise KeyboardInterrupt
        return real_communicate(self, *args, **kwargs)

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(subprocess.Popen, "communicate", interrupt_the_first_wait)
        with pytest.raises(KeyboardInterrupt):
            run(f'{PYTHON} -c "print(1)"')

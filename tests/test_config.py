"""Which source of a setting wins: command line, then environment, then default."""

import re
from pathlib import Path

from axiom import config


def test_defaults_when_nothing_is_set(monkeypatch):
    monkeypatch.delenv("AXIOM_HOST", raising=False)
    monkeypatch.delenv("AXIOM_MODEL", raising=False)

    settings = config.resolve([])

    assert settings.host == config.DEFAULT_HOST
    # AC 2. There is no default model to fall back to - naming nothing is a
    # real state, and it is what sends a run to the host's list.
    assert settings.model is None
    assert settings.debug_max_context is None


def test_axiom_carries_no_model_name_of_its_own():
    """AC 2, and it is not provable by a passing behaviour test.

    A leftover default would sit unused on the happy path and quietly become
    the fallback again the first time someone reached for one, so this asserts
    the absence directly rather than asserting a behaviour that would hold
    either way.
    """
    assert not hasattr(config, "DEFAULT_MODEL")

    source = Path(config.__file__).parent
    named = [
        f"{file.name}:{number}: {line.strip()}"
        for file in source.glob("*.py")
        for number, line in enumerate(file.read_text(encoding="utf-8").splitlines(), 1)
        # A model name is `family:tag`. Matched inside a string literal only,
        # so the prose in a comment explaining why the default was removed is
        # not itself mistaken for the default coming back. Wide enough for
        # every tag shape on this machine - `7b`, `e2b`, `9b`, `latest` - since
        # a pattern that only caught digits would miss `gemma4:e2b` entirely.
        if re.search(r"""['"][A-Za-z0-9._-]+:[A-Za-z0-9._-]+['"]""", line)
    ]
    assert named == []


def test_environment_beats_the_default(monkeypatch):
    monkeypatch.setenv("AXIOM_HOST", "http://elsewhere:1234")
    monkeypatch.setenv("AXIOM_MODEL", "gemma4:e2b")

    settings = config.resolve([])

    assert settings.host == "http://elsewhere:1234"
    assert settings.model == "gemma4:e2b"


def test_the_command_line_beats_the_environment(monkeypatch):
    monkeypatch.setenv("AXIOM_HOST", "http://from-env:1234")
    monkeypatch.setenv("AXIOM_MODEL", "from-env")

    settings = config.resolve(["--host", "http://from-flag:9999", "--model", "flag"])

    assert settings.host == "http://from-flag:9999"
    assert settings.model == "flag"


def test_the_debug_override_arrives_as_a_number(monkeypatch):
    monkeypatch.setenv("AXIOM_DEBUG_MAX_CONTEXT", "500")
    assert config.resolve([]).debug_max_context == 500


def test_settings_do_not_change_after_they_are_resolved():
    """A run's settings are decided once - nothing downstream may edit them."""
    settings = config.resolve([])
    try:
        settings.host = "http://mutated"
    except Exception:
        return
    raise AssertionError("Settings should be frozen")


def test_tool_settings_have_defaults(monkeypatch):
    """AC 32, 33, 34: each has a stated default."""
    for name in ("AXIOM_WORKING_DIRECTORY", "AXIOM_COMMAND_TIMEOUT", "AXIOM_TOOLS"):
        monkeypatch.delenv(name, raising=False)

    settings = config.resolve([])

    assert settings.working_directory is None, "default is where axiom was started"
    assert settings.command_timeout == config.DEFAULT_COMMAND_TIMEOUT
    assert settings.tools_enabled is True


def test_tool_settings_can_be_overridden_by_environment(monkeypatch):
    monkeypatch.setenv("AXIOM_WORKING_DIRECTORY", "/somewhere")
    monkeypatch.setenv("AXIOM_COMMAND_TIMEOUT", "5")
    monkeypatch.setenv("AXIOM_TOOLS", "off")

    settings = config.resolve([])

    assert settings.working_directory == "/somewhere"
    assert settings.command_timeout == 5.0
    assert settings.tools_enabled is False


def test_tool_settings_can_be_overridden_on_the_command_line(monkeypatch):
    monkeypatch.setenv("AXIOM_WORKING_DIRECTORY", "/from-env")
    monkeypatch.setenv("AXIOM_COMMAND_TIMEOUT", "5")

    settings = config.resolve(
        ["--working-directory", "/from-flag", "--command-timeout", "90", "--no-tools"]
    )

    assert settings.working_directory == "/from-flag"
    assert settings.command_timeout == 90.0
    assert settings.tools_enabled is False


def test_tools_stay_on_unless_the_value_means_off(monkeypatch):
    """A stray AXIOM_TOOLS=yes must not silently disable them."""
    for value in ("on", "yes", "1", "true", ""):
        monkeypatch.setenv("AXIOM_TOOLS", value)
        assert config.resolve([]).tools_enabled is True

    for value in ("off", "0", "false", "no", "OFF"):
        monkeypatch.setenv("AXIOM_TOOLS", value)
        assert config.resolve([]).tools_enabled is False


def test_web_settings_have_defaults(monkeypatch):
    """AC 28."""
    for name in (
        "AXIOM_SEARCH_RESULTS",
        "AXIOM_FETCH_TIMEOUT",
        "AXIOM_PAGE_CHARACTERS",
        "AXIOM_WEB",
    ):
        monkeypatch.delenv(name, raising=False)

    settings = config.resolve([])

    assert settings.search_results == config.DEFAULT_SEARCH_RESULTS
    assert settings.fetch_timeout == config.DEFAULT_FETCH_TIMEOUT
    assert settings.page_characters == config.DEFAULT_PAGE_CHARACTERS
    assert settings.web_enabled is True


def test_web_settings_take_environment_then_command_line(monkeypatch):
    monkeypatch.setenv("AXIOM_SEARCH_RESULTS", "3")
    monkeypatch.setenv("AXIOM_FETCH_TIMEOUT", "9")
    monkeypatch.setenv("AXIOM_PAGE_CHARACTERS", "1000")

    from_env = config.resolve([])
    assert (from_env.search_results, from_env.fetch_timeout) == (3, 9.0)
    assert from_env.page_characters == 1000

    from_flags = config.resolve(
        ["--search-results", "8", "--fetch-timeout", "2", "--page-characters", "50"]
    )
    assert (from_flags.search_results, from_flags.fetch_timeout) == (8, 2.0)
    assert from_flags.page_characters == 50


def test_switching_off_the_web_leaves_the_other_tools_on():
    """AC 29: --no-web is not --no-tools. Losing read_file because the network
    was switched off would be a surprise."""
    settings = config.resolve(["--no-web"])

    assert settings.web_enabled is False
    assert settings.tools_enabled is True


def test_switching_off_tools_switches_off_the_web_too():
    """The obvious answer rather than the clever one."""
    settings = config.resolve(["--no-tools"])

    assert settings.tools_enabled is False
    assert settings.web_enabled is False


def test_both_switches_together_are_not_a_puzzle():
    settings = config.resolve(["--no-tools", "--no-web"])

    assert settings.tools_enabled is False
    assert settings.web_enabled is False


def test_the_web_can_be_switched_off_by_environment(monkeypatch):
    monkeypatch.setenv("AXIOM_WEB", "off")
    assert config.resolve([]).web_enabled is False

    monkeypatch.setenv("AXIOM_WEB", "on")
    assert config.resolve([]).web_enabled is True

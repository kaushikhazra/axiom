"""Which source of a setting wins: command line, then environment, then default."""

from axiom import config


def test_defaults_when_nothing_is_set(monkeypatch):
    monkeypatch.delenv("AXIOM_HOST", raising=False)
    monkeypatch.delenv("AXIOM_MODEL", raising=False)

    settings = config.resolve([])

    assert settings.host == config.DEFAULT_HOST
    assert settings.model == config.DEFAULT_MODEL
    assert settings.debug_max_context is None


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

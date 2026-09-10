"""Gmail, read-only (#89).

**No test here touches Google.** The service is a fake with the same call shape
the real client has - `users().messages().list(...).execute()` - and the flow is
never run, because a test that opened a browser would be a test nobody could run
unattended.

The credential is made up. #89's criteria about substitution and redaction are
about what axiom does with a value, not about the value being real.
"""

import os
from pathlib import Path

import pytest

from axiom import mail, tools


class FakeExecutable:
    """One `.execute()` away from a result, as every Google call is."""

    def __init__(self, result):
        self._result = result

    def execute(self):
        return self._result


class FakeMessages:
    """`users().messages()`, recording what it was asked for."""

    def __init__(self, listed, headers=None, page=None):
        self.listed = listed
        self.headers = headers or {}
        self.page = page
        self.calls = []

    def list(self, userId, q, maxResults):  # noqa: N803
        self.calls.append(("list", q, maxResults))
        found = {"messages": [{"id": one} for one in self.listed]}
        if self.page:
            found["nextPageToken"] = self.page
        return FakeExecutable(found)

    def get(self, userId, id, format, metadataHeaders):  # noqa: A002, N803
        self.calls.append(("get", id))
        named = self.headers.get(id, {})
        return FakeExecutable(
            {
                "payload": {
                    "headers": [
                        {"name": name, "value": value} for name, value in named.items()
                    ]
                }
            }
        )


class FakeService:
    def __init__(self, messages):
        self._messages = messages

    def users(self):
        return self

    def messages(self):
        return self._messages


def mailbox_for(messages, tmp_path):
    """A mailbox that hands back a fake service and never runs a flow."""
    box = mail.Mailbox(
        client_id="made-up-id",
        client_secret="made-up-secret",
        token_file=tmp_path / "token.json",
    )
    box._service = FakeService(messages)
    return box


# -- what is offered, and why not ------------------------------------------


def test_nothing_configured_says_which_variables(monkeypatch):
    """AC 23. Both names, because either one is what the user has to set."""
    monkeypatch.delenv(mail.CLIENT_ID, raising=False)
    monkeypatch.delenv(mail.CLIENT_SECRET, raising=False)
    box = mail.from_environment()
    assert not box.configured
    assert mail.CLIENT_ID in box.problem
    assert mail.CLIENT_SECRET in box.problem


def test_half_configured_names_the_missing_one(monkeypatch):
    """AC 24. A user who set one and missed the other is told which."""
    monkeypatch.setenv(mail.CLIENT_ID, "made-up-id")
    monkeypatch.delenv(mail.CLIENT_SECRET, raising=False)
    box = mail.from_environment()
    assert not box.configured
    assert box.problem == mail.NO_SECRET

    monkeypatch.delenv(mail.CLIENT_ID)
    monkeypatch.setenv(mail.CLIENT_SECRET, "made-up-secret")
    assert mail.from_environment().problem == mail.NO_ID


def test_configured_has_no_problem(monkeypatch):
    monkeypatch.setenv(mail.CLIENT_ID, "made-up-id")
    monkeypatch.setenv(mail.CLIENT_SECRET, "made-up-secret")
    box = mail.from_environment()
    assert box.configured
    assert box.problem == ""


# -- what a run is offered -------------------------------------------------


def test_nothing_configured_offers_no_mail_tool():
    """AC 1. A run with no credentials behaves exactly as it does today.

    Not "the tool is there and refuses" - the tool is not there. #75 measured
    what an unusable tool costs: 396 tokens on every request, for four of them.
    """
    offered = tools.without_unusable_mail_tools(tools.declarations(), None)
    names = {tool["function"]["name"] for tool in offered}
    assert names.isdisjoint(tools.MAIL_TOOLS)
    assert len(offered) == len(tools.REGISTRY) - len(tools.MAIL_TOOLS)


def test_half_configured_offers_no_mail_tool(monkeypatch):
    """A credential that cannot work is not a credential."""
    monkeypatch.setenv(mail.CLIENT_ID, "made-up-id")
    monkeypatch.delenv(mail.CLIENT_SECRET, raising=False)
    offered = tools.without_unusable_mail_tools(
        tools.declarations(), mail.from_environment()
    )
    names = {tool["function"]["name"] for tool in offered}
    assert names.isdisjoint(tools.MAIL_TOOLS)


def test_configured_offers_the_mail_tools(monkeypatch):
    """AC 2. Configured, and the tools are there to be counted."""
    monkeypatch.setenv(mail.CLIENT_ID, "made-up-id")
    monkeypatch.setenv(mail.CLIENT_SECRET, "made-up-secret")
    offered = tools.without_unusable_mail_tools(
        tools.declarations(), mail.from_environment()
    )
    names = {tool["function"]["name"] for tool in offered}
    assert tools.MAIL_TOOLS <= names
    assert len(offered) == len(tools.REGISTRY)


# -- the scope is the guarantee --------------------------------------------


def test_the_only_scope_is_read_only():
    """AC 28. Not a check that refuses a send - a permission never asked for."""
    assert mail.SCOPE.endswith("gmail.readonly")
    assert "send" not in mail.SCOPE
    assert "modify" not in mail.SCOPE


def test_no_tool_can_send_or_delete():
    """AC 27. Read is the whole surface axiom offers."""
    for name in tools.MAIL_TOOLS:
        assert name in tools.REGISTRY
        for forbidden in ("send", "delete", "archive", "trash", "modify"):
            assert forbidden not in name


# -- where the grant is kept -----------------------------------------------


def test_token_lives_outside_any_repository():
    """AC 14. Under the user's home, never under the working directory.

    `.axiom/` is relative to wherever axiom was started, which for a developer
    is this repository - and a token is the one thing that must not land there.
    """
    assert mail.DEFAULT_TOKEN_FILE.is_absolute()
    assert str(mail.DEFAULT_TOKEN_FILE).startswith(str(Path.home()))
    assert Path.cwd() not in mail.DEFAULT_TOKEN_FILE.parents


def test_token_file_can_be_pointed_elsewhere(monkeypatch, tmp_path):
    monkeypatch.setenv(mail.CLIENT_ID, "made-up-id")
    monkeypatch.setenv(mail.CLIENT_SECRET, "made-up-secret")
    monkeypatch.setenv(mail.TOKEN_FILE, str(tmp_path / "elsewhere.json"))
    assert mail.from_environment().token_file == tmp_path / "elsewhere.json"


def test_forgetting_removes_the_grant(tmp_path):
    """AC 15, AC 16. The next call finds no cache, so it has to ask again."""
    token = tmp_path / "token.json"
    token.write_text("{}", encoding="utf-8")
    box = mail.Mailbox(
        client_id="made-up-id", client_secret="made-up-secret", token_file=token
    )
    box._service = object()

    assert box.forget() is True
    assert not token.exists()
    assert box._service is None
    # Nothing to forget the second time, and it says so rather than raising.
    assert box.forget() is False


def test_an_unreadable_cache_is_no_cache(tmp_path):
    """A file the user never asked about does not crash a run."""
    token = tmp_path / "token.json"
    token.write_text("not json at all", encoding="utf-8")
    box = mail.Mailbox(
        client_id="made-up-id", client_secret="made-up-secret", token_file=token
    )
    assert box.stored() is None


@pytest.mark.skipif(os.name == "nt", reason="chmod does not restrict on Windows")
def test_the_grant_is_readable_only_by_the_user(tmp_path):
    """AC 14, on the platform where the mode means something.

    On Windows the location is the protection - `C:/Users/<name>` is ACL'd to
    that user - and `os.chmod` moves the read-only bit and nothing else. That
    is why this asserts nothing there rather than asserting something false.
    """

    class Fake:
        def to_json(self):
            return "{}"

    token = tmp_path / "token.json"
    box = mail.Mailbox(token_file=token)
    box._remember(Fake())
    assert token.stat().st_mode & 0o777 == 0o600


# -- searching --------------------------------------------------------------


def test_search_returns_sender_subject_and_date(tmp_path):
    """AC 17. All three, plus the id that AC 18 will need."""
    messages = FakeMessages(
        ["m1"],
        {
            "m1": {
                "From": "Ada <ada@example.com>",
                "Subject": "the analytical engine",
                "Date": "Tue, 9 Sep 2026 11:04:00 +0530",
            }
        },
    )
    result = tools.run(
        "search_mail", {"query": "engine"}, mailbox=mailbox_for(messages, tmp_path)
    )
    assert "ada@example.com" in result
    assert "the analytical engine" in result
    assert "9 Sep 2026" in result
    assert "m1" in result


def test_a_search_matching_nothing_says_so(tmp_path):
    """AC 23. Not an empty string - a model told nothing came back invents."""
    messages = FakeMessages([])
    result = tools.run(
        "search_mail", {"query": "nothing"}, mailbox=mailbox_for(messages, tmp_path)
    )
    assert "no messages match" in result
    assert "nothing" in result


def test_a_bounded_search_says_it_was_bounded(tmp_path):
    """AC 24. Said only when the limit actually bound the answer."""
    ids = [f"m{n}" for n in range(tools.MAIL_RESULTS)]
    messages = FakeMessages(ids, page="more-to-come")
    result = tools.run(
        "search_mail", {"query": "everything"}, mailbox=mailbox_for(messages, tmp_path)
    )
    assert f"the first {tools.MAIL_RESULTS}" in result
    assert "more matches" in result


def test_an_unbounded_search_does_not_claim_truncation(tmp_path):
    """The other half of AC 24, and the one a happy path would miss."""
    messages = FakeMessages(["m1", "m2"])
    result = tools.run(
        "search_mail", {"query": "two"}, mailbox=mailbox_for(messages, tmp_path)
    )
    assert "more matches" not in result


def test_an_empty_search_reaches_google_not_at_all(tmp_path):
    """AC 26. Refused with a reason, and no call made."""
    messages = FakeMessages(["m1"])
    box = mailbox_for(messages, tmp_path)
    result = tools.run("search_mail", {"query": "   "}, mailbox=box)
    assert result.startswith("error:")
    assert messages.calls == []


def test_the_limit_is_axioms_and_not_the_models():
    """A model cannot widen the search by asking - it is not in the schema."""
    declared = tools.REGISTRY["search_mail"].parameters["properties"]
    assert set(declared) == {"query"}
    assert tools.run("search_mail", {"query": "x", "maxResults": 500}).startswith(
        "error:"
    )


def test_no_mailbox_says_so_rather_than_crashing(tmp_path):
    """A session without mail tells a model why nothing happened."""
    assert tools.run("search_mail", {"query": "anything"}) == tools.NO_MAIL


# -- what a refusal costs ---------------------------------------------------


def test_a_refused_grant_becomes_an_error_not_an_exception(tmp_path):
    """AC 5, AC 6, AC 10, AC 35. No permission, session still usable."""
    box = mail.Mailbox(
        client_id="made-up-id",
        client_secret="made-up-secret",
        token_file=tmp_path / "token.json",
        refused="permission was declined, so Gmail is not available this session",
    )
    result = tools.run("search_mail", {"query": "anything"}, mailbox=box)
    assert result.startswith("error:")
    assert "declined" in result


def test_a_non_terminal_run_is_told_what_to_do_instead(tmp_path):
    """AC 21, AC 37. No browser, and a sentence rather than silence."""
    box = mail.Mailbox(
        client_id="made-up-id",
        client_secret="made-up-secret",
        token_file=tmp_path / "token.json",
        interactive=False,
    )
    with pytest.raises(mail.Refused) as refused:
        box.service()
    assert "not a terminal" in str(refused.value)


def test_a_failed_flow_never_carries_the_redirect(tmp_path):
    """AC 29, AC 30. `oauthlib` puts the whole redirect in some of its errors,
    and that redirect carries the authorization code."""
    leaky = Exception("error=access_denied&code=4/0AeanS0-secret-code-here&state=xyz")
    said = mail._why(leaky)
    assert "4/0AeanS0" not in said
    assert "secret-code-here" not in said
    assert "declined" in said

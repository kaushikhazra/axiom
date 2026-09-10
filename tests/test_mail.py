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


# -- what a whole run offers, through the path a user takes ----------------


def start(capsys, monkeypatch, tmp_path, argv=(), stdout_tty=True):
    """One axiom run, started and exited, as `test_tool_cost` does it."""
    from axiom import main, models
    from conftest import StubBackend, feed

    monkeypatch.setattr(
        models, "DEFAULT_CHOICE_FILE", tmp_path / ".axiom" / "model.json"
    )
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    monkeypatch.setattr("sys.stdout.isatty", lambda: stdout_tty)
    made = StubBackend(models=["big:70b"])
    feed(monkeypatch, ["/exit"])
    main([*argv, "--model", "big:70b"], using=made)
    return capsys.readouterr()


def test_a_run_with_no_credentials_says_what_it_always_said(
    capsys, monkeypatch, tmp_path
):
    """AC 1, through the startup line rather than through the filter.

    The count is the observable. A user with no Google account must not be able
    to tell that #89 shipped.
    """
    monkeypatch.delenv(mail.CLIENT_ID, raising=False)
    monkeypatch.delenv(mail.CLIENT_SECRET, raising=False)
    out = start(capsys, monkeypatch, tmp_path).out
    expected = len(tools.REGISTRY) - len(tools.SKILL_TOOLS - {"write_skill"})
    assert f"{expected - len(tools.MAIL_TOOLS)} tools" in out
    assert "mail" not in out.lower()


def test_a_run_with_credentials_counts_the_mail_tools(capsys, monkeypatch, tmp_path):
    """AC 2. The startup count includes them - which is what AC 2 asks for,
    rather than the filter returning the right list."""
    monkeypatch.setenv(mail.CLIENT_ID, "made-up-id")
    monkeypatch.setenv(mail.CLIENT_SECRET, "made-up-secret")
    out = start(capsys, monkeypatch, tmp_path).out
    expected = len(tools.REGISTRY) - len(tools.SKILL_TOOLS - {"write_skill"})
    assert f"{expected} tools" in out


def test_a_redirected_run_cannot_open_a_browser(capsys, monkeypatch, tmp_path):
    """AC 37. The guard is set from the streams, at the one place a mailbox is
    built - not remembered at each call site."""
    monkeypatch.setenv(mail.CLIENT_ID, "made-up-id")
    monkeypatch.setenv(mail.CLIENT_SECRET, "made-up-secret")
    built = []
    real = mail.from_environment
    monkeypatch.setattr(
        mail,
        "from_environment",
        lambda interactive=True: built.append(interactive) or real(interactive),
    )
    start(capsys, monkeypatch, tmp_path, stdout_tty=False)
    assert built == [False]


def test_a_terminal_run_may_open_a_browser(capsys, monkeypatch, tmp_path):
    monkeypatch.setenv(mail.CLIENT_ID, "made-up-id")
    monkeypatch.setenv(mail.CLIENT_SECRET, "made-up-secret")
    built = []
    real = mail.from_environment
    monkeypatch.setattr(
        mail,
        "from_environment",
        lambda interactive=True: built.append(interactive) or real(interactive),
    )
    start(capsys, monkeypatch, tmp_path, stdout_tty=True)
    assert built == [True]


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


# -- reading one message ----------------------------------------------------


def encoded(text: str) -> str:
    """As Gmail sends a body: base64url, padding stripped."""
    import base64

    return base64.urlsafe_b64encode(text.encode("utf-8")).decode().rstrip("=")


def part(mime, text=None, filename="", size=None, parts=None):
    """One node of a Gmail payload tree."""
    node = {"mimeType": mime, "filename": filename}
    if text is not None:
        node["body"] = {"data": encoded(text)}
    if size is not None:
        node["body"] = {"size": size}
    if parts is not None:
        node["parts"] = parts
    return node


class FakeOneMessage:
    """`users().messages()` for a single `get(format="full")`."""

    def __init__(self, payload, headers=None):
        self.payload = payload
        self.headers = headers or {}
        self.calls = []

    def get(self, userId, id, format, metadataHeaders=None):  # noqa: A002, N803
        self.calls.append(("get", id, format))
        return FakeExecutable(
            {
                "payload": {
                    **self.payload,
                    "headers": [
                        {"name": name, "value": value}
                        for name, value in self.headers.items()
                    ],
                }
                # Deliberately no top-level "headers". Gmail puts them under
                # `payload` and nowhere else, and a fake that carries them in
                # both places would pass whichever one the code read.
            }
        )


def read(payload, tmp_path, headers=None, message_id="m1"):
    messages = FakeOneMessage(payload, headers)
    box = mailbox_for(messages, tmp_path)
    return tools.run("read_mail", {"message_id": message_id}, mailbox=box), messages


def test_a_plain_single_part_body_is_read(tmp_path):
    """AC 18, AC 19 - the shape everything else is measured against."""
    result, _ = read(
        part("text/plain", "the difference engine is not the analytical one"),
        tmp_path,
        {"From": "Ada", "Subject": "engines", "Date": "Tue, 9 Sep 2026"},
    )
    assert "the difference engine is not the analytical one" in result
    assert "Ada" in result
    assert "engines" in result


def test_padding_that_gmail_stripped_is_put_back(tmp_path):
    """AC 19. base64url with no padding is what Gmail actually sends, and a
    body whose length is not a multiple of four raises without this."""
    for length in range(1, 8):
        body = "x" * length
        result, _ = read(part("text/plain", body), tmp_path)
        assert body in result


def test_multipart_alternative_prefers_the_plain_half(tmp_path):
    """AC 19. Both halves say the same thing; the plain one costs less window
    and does not teach the model to quote tags."""
    result, _ = read(
        part(
            "multipart/alternative",
            parts=[
                part("text/plain", "plain words"),
                part("text/html", "<p>html words</p>"),
            ],
        ),
        tmp_path,
    )
    assert "plain words" in result
    assert "<p>" not in result
    assert "html words" not in result


def test_html_only_is_stripped_rather_than_handed_over(tmp_path):
    """AC 19. No plain part anywhere, so the HTML is all there is."""
    result, _ = read(
        part(
            "multipart/alternative",
            parts=[
                part("text/html", "<html><body><p>only html here</p></body></html>")
            ],
        ),
        tmp_path,
    )
    assert "only html here" in result
    assert "<p>" not in result
    assert "<html>" not in result


def test_a_text_part_nested_under_a_mixed_part_is_found(tmp_path):
    """AC 19. An attachment pushes the body a level down, which is the shape a
    single-level reader gets wrong."""
    result, _ = read(
        part(
            "multipart/mixed",
            parts=[
                part(
                    "multipart/alternative",
                    parts=[part("text/plain", "buried but readable")],
                ),
                part("application/pdf", filename="report.pdf", size=2048),
            ],
        ),
        tmp_path,
    )
    assert "buried but readable" in result


def test_a_message_with_no_readable_part_says_so(tmp_path):
    """AC 19's last case. Not an empty string - a model told nothing came back
    answers from memory, which is the failure #40 exists to prevent."""
    result, _ = read(part("image/png", filename="", size=99), tmp_path)
    assert "no part that can be shown as text" in result


def test_an_attachment_is_named_not_dropped(tmp_path):
    """AC 20. Filename, type and size - and nothing fetched."""
    result, messages = read(
        part(
            "multipart/mixed",
            parts=[
                part("text/plain", "see attached"),
                part("application/pdf", filename="report.pdf", size=2048),
            ],
        ),
        tmp_path,
    )
    assert "report.pdf" in result
    assert "application/pdf" in result
    assert "2048" in result
    assert "see attached" in result


def test_reading_never_fetches_an_attachment(tmp_path):
    """AC 31. Proved by what the fake was asked for, not by the absence of a
    file - a test that checks for no file passes on a machine where the write
    silently failed."""
    _, messages = read(
        part(
            "multipart/mixed",
            parts=[
                part("text/plain", "body"),
                part("application/pdf", filename="big.pdf", size=9_000_000),
            ],
        ),
        tmp_path,
    )
    assert [name for name, *_ in messages.calls] == ["get"]
    assert not hasattr(messages, "attachments")


def test_an_empty_id_reaches_google_not_at_all(tmp_path):
    messages = FakeOneMessage(part("text/plain", "never read"))
    box = mailbox_for(messages, tmp_path)
    result = tools.run("read_mail", {"message_id": "  "}, mailbox=box)
    assert result.startswith("error:")
    assert messages.calls == []


def test_reading_asks_for_the_full_message(tmp_path):
    """`metadata` would give the headers and no body at all."""
    _, messages = read(part("text/plain", "words"), tmp_path)
    assert messages.calls[0][2] == "full"


# -- the command ------------------------------------------------------------


def typed(capsys, monkeypatch, tmp_path, lines, configured=True):
    """One run, with lines typed at it, as a user would."""
    from axiom import main, models
    from conftest import StubBackend, feed

    monkeypatch.setattr(
        models, "DEFAULT_CHOICE_FILE", tmp_path / ".axiom" / "model.json"
    )
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    monkeypatch.setattr("sys.stdout.isatty", lambda: True)
    if configured:
        monkeypatch.setenv(mail.CLIENT_ID, "made-up-id")
        monkeypatch.setenv(mail.CLIENT_SECRET, "made-up-secret")
    else:
        monkeypatch.delenv(mail.CLIENT_ID, raising=False)
        monkeypatch.delenv(mail.CLIENT_SECRET, raising=False)
    monkeypatch.setenv(mail.TOKEN_FILE, str(tmp_path / "token.json"))
    made = StubBackend(models=["big:70b"])
    feed(monkeypatch, [*lines, "/exit"])
    main(["--model", "big:70b"], using=made)
    return capsys.readouterr().out, made


def test_mail_with_no_grant_says_the_next_request_will_ask(
    capsys, monkeypatch, tmp_path
):
    """AC 22, the state every run starts in."""
    out, _ = typed(capsys, monkeypatch, tmp_path, ["/mail"])
    assert "holds no permission" in out


def test_mail_with_nothing_configured_still_answers(capsys, monkeypatch, tmp_path):
    """A user who typed it is owed a reason. AC 1 is about startup."""
    out, _ = typed(capsys, monkeypatch, tmp_path, ["/mail"], configured=False)
    assert mail.CLIENT_ID in out


def test_mail_names_the_account_it_can_read(capsys, monkeypatch, tmp_path):
    """AC 22. Which account, and how long the permission runs."""
    token = tmp_path / "token.json"
    token.write_text("{}", encoding="utf-8")

    class Held:
        account = "ada@example.com"
        expiry = "2026-09-17 11:00"

    monkeypatch.setattr(mail.Mailbox, "stored", lambda self: Held())
    out, _ = typed(capsys, monkeypatch, tmp_path, ["/mail"])
    assert "ada@example.com" in out
    assert "2026-09-17" in out


def test_mail_forget_gives_the_permission_back(capsys, monkeypatch, tmp_path):
    """AC 15, AC 16 - and the file is gone, which is what makes the next
    request ask."""
    token = tmp_path / "token.json"
    token.write_text("{}", encoding="utf-8")
    out, _ = typed(capsys, monkeypatch, tmp_path, ["/mail forget"])
    assert "given back" in out
    assert "will ask again" in out
    assert not token.exists()


def test_mail_forget_with_nothing_held_says_so(capsys, monkeypatch, tmp_path):
    """Not "forgotten" - that would leave a user believing they revoked
    something they never granted."""
    out, _ = typed(capsys, monkeypatch, tmp_path, ["/mail forget"])
    assert "nothing to give back" in out


def test_an_unknown_mail_word_is_named(capsys, monkeypatch, tmp_path):
    out, _ = typed(capsys, monkeypatch, tmp_path, ["/mail revoke"])
    assert "no /mail revoke" in out


def test_the_mail_command_never_reaches_the_model(capsys, monkeypatch, tmp_path):
    """Like every other command. `continue` before `messages` is touched."""
    _, made = typed(capsys, monkeypatch, tmp_path, ["/mail", "/mail forget"])
    assert made.streamed == []


def test_a_message_containing_mail_is_a_message(capsys, monkeypatch, tmp_path):
    """#49 AC 9's rule, which every command here follows: matched as a whole
    word, so a message that merely contains it is a message."""
    _, made = typed(capsys, monkeypatch, tmp_path, ["what does /mail do?"])
    assert made.streamed != []


def test_a_pasted_block_starting_with_mail_is_not_a_command(
    capsys, monkeypatch, tmp_path
):
    """#80 AC 13, AC 14. A command is a message of one line."""
    _, made = typed(capsys, monkeypatch, tmp_path, ["/mail forget\nand more text"])
    assert made.streamed != []


# -- what a failed call may say ---------------------------------------------


class Boom:
    """A service whose every call raises. The shape a real one has."""

    def __init__(self, blow):
        self.blow = blow

    def users(self):
        return self

    def messages(self):
        return self

    def list(self, **kw):
        return self

    def get(self, **kw):
        return self

    def execute(self):
        raise self.blow


def blowing(blow, tmp_path):
    made = mail.Mailbox(
        client_id="made-up-id",
        client_secret="made-up-secret",
        token_file=tmp_path / "token.json",
    )
    made._service = Boom(blow)
    return made


def http_error(status, reason="Rate Limit Exceeded", uri="https://example/x"):
    from googleapiclient.errors import HttpError

    class Resp:
        pass

    resp = Resp()
    resp.status = status
    resp.reason = reason
    return HttpError(
        resp, b'{"error": {"message": "' + reason.encode() + b'"}}', uri=uri
    )


def test_a_refresh_failure_never_carries_the_token_endpoint_response(tmp_path):
    """AC 29, AC 30, and the defect cycle 5's sweep found.

    `google/oauth2/_client.py:320` raises
    `RefreshError("No access token in response.", response_data)` - and that
    response is where the **refresh token** lives. Stringified, a two-argument
    exception gives its args tuple, so before this the token went into a tool
    result, to the model and to the screen.
    """
    from google.auth.exceptions import RefreshError

    leaky = RefreshError(
        "No access token in response.",
        {"refresh_token": "1//0gLEAKED", "scope": "gmail.readonly"},
    )
    result = tools.run("search_mail", {"query": "x"}, mailbox=blowing(leaky, tmp_path))
    assert "1//0gLEAKED" not in result
    assert "refresh_token" not in result
    assert "/mail forget" in result


def test_an_http_error_never_carries_the_request_uri(tmp_path):
    """AC 30. `HttpError.__str__` includes `self.uri`. Today the access token
    travels in a header, but the URI carries the user's search either way and
    the class of leak is one library detail away."""
    blow = http_error(
        429, uri="https://gmail.googleapis.com/v1/messages?q=salary&access_token=ya29.X"
    )
    result = tools.run(
        "search_mail", {"query": "salary"}, mailbox=blowing(blow, tmp_path)
    )
    assert "ya29.X" not in result
    assert "access_token" not in result
    assert "gmail.googleapis.com" not in result


def test_rate_limiting_is_named_as_rate_limiting(tmp_path):
    """AC 33. What the user does next differs from a refusal - wait, not
    re-grant - so the two must not read the same."""
    result = tools.run(
        "search_mail", {"query": "x"}, mailbox=blowing(http_error(429), tmp_path)
    )
    assert "rate limiting" in result
    assert "forget" not in result


def test_a_refusal_says_what_google_said(tmp_path):
    """AC 33's other half. Google's `reason` comes from the response body, so
    it carries nothing of ours."""
    blow = http_error(403, reason="Daily Limit Exceeded")
    result = tools.run("search_mail", {"query": "x"}, mailbox=blowing(blow, tmp_path))
    assert "403" in result
    assert "Daily Limit Exceeded" in result


def test_google_being_unreachable_is_reported(tmp_path):
    """AC 32. No status at all is a transport failure, named by its type
    rather than by a message that might quote a URL."""
    from google.auth.exceptions import TransportError

    blow = TransportError("failed to resolve gmail.googleapis.com via 10.0.0.1")
    result = tools.run("search_mail", {"query": "x"}, mailbox=blowing(blow, tmp_path))
    assert "could not be reached" in result
    assert "10.0.0.1" not in result


def test_a_failed_call_leaves_every_other_tool_usable(tmp_path):
    """AC 35. A returned error, never a raised one."""
    result = tools.run(
        "search_mail", {"query": "x"}, mailbox=blowing(http_error(500), tmp_path)
    )
    assert result.startswith("error:")
    assert tools.run("read_file", {"path": str(tmp_path)}).startswith("error:")


def test_reading_one_message_is_wrapped_too(tmp_path):
    """The same guarantee on the other tool - a wrapper on one call site and
    not the other is the shape this defect had in the first place."""
    from google.auth.exceptions import RefreshError

    leaky = RefreshError("No access token in response.", {"refresh_token": "1//0gX"})
    result = tools.run(
        "read_mail", {"message_id": "m1"}, mailbox=blowing(leaky, tmp_path)
    )
    assert "1//0gX" not in result


# -- boundaries, switches and the way out -----------------------------------


def test_a_message_that_does_not_exist_is_reported_as_such(tmp_path):
    """AC 25. Distinct from a refusal, deliberately.

    A model told "Google refused the request" gives up on Gmail; told the id is
    not there, it tries a different id. The wrong lesson is the defect.
    """
    result = tools.run(
        "read_mail", {"message_id": "nope"}, mailbox=blowing(http_error(404), tmp_path)
    )
    assert "no message with that id" in result
    assert "refused" not in result
    assert tools.run("read_file", {"path": str(tmp_path)}).startswith("error:")


def test_no_tools_offers_no_mail_tool_even_when_configured(
    capsys, monkeypatch, tmp_path
):
    """AC 36, first half. Free from `_prepare` returning None - and tested
    anyway, because "free" is what cycle 2 assumed about AC 1 before the
    baseline caught it."""
    monkeypatch.setenv(mail.CLIENT_ID, "made-up-id")
    monkeypatch.setenv(mail.CLIENT_SECRET, "made-up-secret")
    out = start(capsys, monkeypatch, tmp_path, argv=["--no-tools"]).out
    assert "tools" in out.lower()
    for name in tools.MAIL_TOOLS:
        assert name not in out


def test_no_tools_means_nothing_can_reach_the_flow(capsys, monkeypatch, tmp_path):
    """AC 36, the half that matters. With nothing declared there is no call
    that could open a browser - proved by what the model was sent, not by
    reasoning about it."""
    monkeypatch.setenv(mail.CLIENT_ID, "made-up-id")
    monkeypatch.setenv(mail.CLIENT_SECRET, "made-up-secret")
    from axiom import main, models
    from conftest import StubBackend, feed

    monkeypatch.setattr(
        models, "DEFAULT_CHOICE_FILE", tmp_path / ".axiom" / "model.json"
    )
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    monkeypatch.setattr("sys.stdout.isatty", lambda: True)
    made = StubBackend(models=["big:70b"], turns=[["a reply"]])
    feed(monkeypatch, ["hello", "/exit"])
    main(["--no-tools", "--model", "big:70b"], using=made)
    assert made.tools_sent == [None]


def test_a_refused_run_still_exits_zero(capsys, monkeypatch, tmp_path):
    """AC 40. A refusal returns an `error:` string; nothing raises, so no
    ordinary way out changes its status."""
    box = mail.Mailbox(
        client_id="made-up-id",
        client_secret="made-up-secret",
        token_file=tmp_path / "token.json",
        refused="permission was declined, so Gmail is not available this session",
    )
    assert tools.run("search_mail", {"query": "x"}, mailbox=box).startswith("error:")
    # Both ordinary ways out, after a refusal, with no SystemExit raised.
    for last in ("/exit", None):
        lines = ["/mail"] if last is None else ["/mail", last]
        typed(capsys, monkeypatch, tmp_path, lines)


def test_the_flow_closes_its_listener_on_the_timeout_path(monkeypatch):
    """AC 39. `run_local_server`'s `finally` calls `server_close()`, and the
    timeout path raises from inside the `try`, so it is covered too
    (`google_auth_oauthlib/flow.py`).

    **This asserts the close happened, not that the port came free**, and that
    is a correction rather than a preference. The obvious version - bind the
    port again afterwards and see that it works - was written first and probed:
    with `server_close` replaced by a no-op it *still rebound*, because
    refcounting drops the socket when the server goes out of scope. It would
    have been green against a library that leaked, on the one criterion #43
    AC 26 and AC 27 exist in this repo because of.

    No network is touched: the authorization URL is built locally and the wait
    times out before anything is sent.
    """
    import wsgiref.simple_server

    from google_auth_oauthlib.flow import InstalledAppFlow, WSGITimeoutError

    closed = []
    real_close = wsgiref.simple_server.WSGIServer.server_close
    monkeypatch.setattr(
        wsgiref.simple_server.WSGIServer,
        "server_close",
        lambda self: closed.append(True) or real_close(self),
    )

    flow = InstalledAppFlow.from_client_config(
        {
            "installed": {
                "client_id": "made-up-id",
                "client_secret": "made-up-secret",
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
            }
        },
        [mail.SCOPE],
    )
    with pytest.raises(WSGITimeoutError):
        flow.run_local_server(
            port=0,
            open_browser=False,
            authorization_prompt_message=None,
            timeout_seconds=0.1,
        )
    assert closed == [True]


def test_axiom_asks_for_a_bounded_wait_so_the_listener_cannot_sit_forever():
    """AC 10 and AC 39 together, on axiom's side of the line.

    The library closes the listener when the wait ends; what makes the wait
    *end* is `timeout_seconds`, which is axiom's to pass. Left at the library's
    default of `None` there is no timeout at all, and a user who closed the tab
    would leave a socket held for the life of the run.
    """
    import inspect

    source = inspect.getsource(mail.Mailbox._granted)
    assert "timeout_seconds=self.timeout" in source
    assert mail.GRANT_TIMEOUT > 0


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

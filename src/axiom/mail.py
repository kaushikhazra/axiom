"""The user's own mail, read-only.

`tools.py` is what axiom can do on this machine and `servers.py` is what someone
else's process offers. This is a third thing: an account that belongs to the
user, reached with their permission, which they granted in a browser and can
take back.

**Read-only, and structurally so.** The one scope asked for is
`gmail.readonly` (#89 AC 28), so a model that improvises its way to a send gets
a 403 from Google rather than a sent message. Nothing here can send, delete,
archive, or modify - not because a check refuses it, but because the permission
was never asked for.

**Nothing is imported from Google at module level.** `googleapiclient.discovery`
costs 1.196s to import, measured, and `tools.py` imports this module - so a
module-level import would put 1.2s on every axiom start, every test collection,
and every `--help`. The imports sit inside the functions that need them, which
is what `servers.py` already does with `streamable_http_client` for the same
reason.
"""

import os
from dataclasses import dataclass, field
from pathlib import Path

# Read, and nothing else. Not a list that could grow: a second entry here is a
# decision about what a model may do to someone's account, and it belongs in an
# issue rather than in a tuple.
SCOPE = "https://www.googleapis.com/auth/gmail.readonly"

# Where the grant is remembered between runs. **Under the user's home, never
# under the working directory** (AC 14): `.axiom/` is relative to wherever
# axiom was started, which for a developer is the repository - and a token is
# the one thing that must not land there.
DEFAULT_TOKEN_FILE = Path.home() / ".axiom" / "gmail-token.json"

# The environment axiom already reads settings from, in the shape it already
# reads them (`config.py`). Not a `client_secret.json` on a path frozen at
# install time - that is the hardcoding this project does not do, and it would
# break the moment the folder were renamed.
CLIENT_ID = "AXIOM_GOOGLE_CLIENT_ID"
CLIENT_SECRET = "AXIOM_GOOGLE_CLIENT_SECRET"
TOKEN_FILE = "AXIOM_GOOGLE_TOKEN"

# How long the browser flow may stay open before it is abandoned (AC 10). Long
# enough to find a password manager, short enough that a user who walked away
# gets their session back rather than a process waiting forever.
GRANT_TIMEOUT = 180.0

# What the user is told when Gmail cannot be offered. Named one by one rather
# than counted, which is `Settings.mcp_problems`'s reasoning: a variable the
# user has not set is fixed by setting that variable, and a count does not say
# which (AC 23, AC 24, AC 25).
NO_CREDENTIALS = (
    f"neither {CLIENT_ID} nor {CLIENT_SECRET} is set, so Gmail is not offered"
)
NO_ID = f"{CLIENT_SECRET} is set but {CLIENT_ID} is not, so Gmail is not offered"
NO_SECRET = f"{CLIENT_ID} is set but {CLIENT_SECRET} is not, so Gmail is not offered"


@dataclass
class Grant:
    """What a stored permission is, without saying what it holds.

    Returned by `status()` for AC 22 - the user asks which account axiom is
    reading and when the permission was granted. **The token is not a field.**
    Nothing that reaches a caller carries the secret, so no caller has to
    remember not to print it (AC 29).
    """

    account: str = ""
    granted: str = ""
    held: bool = False


@dataclass
class Mailbox:
    """The session's access to one Gmail account.

    Session state, mutable, injected into the tools that need it - the same
    category as `schedule.Schedule` and `skills.Library`, and deliberately the
    same shape. It is not a field on `Limits` for the reason `needs_schedule`
    gives: `Limits` is frozen and holds settings that belong to the user, and
    this is neither frozen nor a setting.

    **The browser flow does not run on construction.** A run whose stored
    permission is still good opens no browser (AC 3), and the flow belongs to
    the first request that actually needs Gmail (AC 4). So this object is cheap
    to build, is built whether or not Gmail will ever be used, and does nothing
    until a tool asks it for a service.
    """

    client_id: str = ""
    client_secret: str = ""
    token_file: Path = DEFAULT_TOKEN_FILE
    # Whether a browser may be opened at all. False for a run that is not a
    # terminal (AC 37): a redirected or piped run has nobody watching, and
    # `run_local_server` opens one by default and will not ask.
    interactive: bool = True
    timeout: float = GRANT_TIMEOUT
    # Set once the flow has been abandoned or declined, so a turn that failed to
    # get permission does not reopen the browser on the model's next call. Reset
    # by `forget`.
    refused: str = ""
    _service: object | None = field(default=None, repr=False)

    @property
    def configured(self) -> bool:
        """Whether this run has credentials to attempt anything with."""
        return bool(self.client_id and self.client_secret)

    @property
    def problem(self) -> str:
        """Why Gmail is not offered, or empty if it is.

        Three states rather than one, because the fix differs: neither variable
        set is a user who has not configured Gmail, and one of the two set is a
        user who tried and missed one (AC 23, AC 24).
        """
        if self.client_id and self.client_secret:
            return ""
        if not self.client_id and not self.client_secret:
            return NO_CREDENTIALS
        return NO_ID if self.client_secret else NO_SECRET

    # -- the grant ---------------------------------------------------------

    def stored(self):
        """The cached credentials, or None. Never runs a flow.

        Returns whatever was on disk even when it has expired: telling a live
        grant from a dead one is `service`'s job, and this one exists so
        `status` and `forget` can answer without opening a browser.
        """
        from google.oauth2.credentials import Credentials

        if not self.token_file.exists():
            return None
        try:
            return Credentials.from_authorized_user_file(str(self.token_file), [SCOPE])
        except (ValueError, OSError):
            # A cache that cannot be read is a cache that is not there. It gets
            # replaced by the next successful grant rather than crashing a run
            # over a file the user never asked about.
            return None

    def _remember(self, credentials) -> None:  # noqa: ANN001
        """Write the grant where the next run will find it (AC 11, AC 14).

        **Under the user's home, and `0o600`.** On POSIX that is the whole
        answer. On Windows it is not: `os.chmod` moves the read-only bit and
        nothing else, so the mode says nothing about who may read the file.

        What actually restricts it there is the location. `C:/Users/<name>` is
        ACL'd to that user and to administrators when Windows creates it, and
        every other account on the machine is excluded by inheritance. That is
        the protection, `chmod` is not, and an ACL of our own would be a second
        mechanism claiming to do what the first already does.

        This is a decision, not an oversight, and it is written down so nobody
        re-opens it on seeing `chmod` on a Windows path.
        """
        self.token_file.parent.mkdir(parents=True, exist_ok=True)
        self.token_file.write_text(credentials.to_json(), encoding="utf-8")
        os.chmod(self.token_file, 0o600)

    def forget(self) -> bool:
        """Drop the stored grant. True if there was one (AC 15, AC 16).

        The next call that needs Gmail finds no cache and asks again, which is
        what "takes effect immediately" means here - there is no live session to
        tear down, because `_service` is rebuilt from credentials that are now
        gone.
        """
        self._service = None
        self.refused = ""
        if not self.token_file.exists():
            return False
        self.token_file.unlink()
        return True

    def status(self) -> Grant:
        """What axiom holds, without the secret it holds it with (AC 22)."""
        held = self.stored()
        if held is None:
            return Grant()
        return Grant(
            account=getattr(held, "account", "") or "",
            granted=str(getattr(held, "expiry", "") or ""),
            held=True,
        )

    def service(self, announce=None):  # noqa: ANN001
        """A Gmail client, granting permission first if that is what it takes.

        Returns the service, or raises `Refused` carrying what the user should
        be told. The tools turn that into an `error:` string - they do not
        decide what happened, because deciding it here keeps every reason in
        one place.

        The order is AC 3, AC 12, AC 13 and AC 4, in that order and for that
        reason: a good cached grant opens nothing, an expired one is renewed
        silently, one that cannot be renewed falls through to the flow rather
        than failing, and only a run with nothing usable reaches the browser.
        """
        from google.auth.exceptions import RefreshError
        from google.auth.transport.requests import Request
        from googleapiclient.discovery import build

        if self._service is not None:
            return self._service
        if not self.configured:
            raise Refused(self.problem)
        if self.refused:
            raise Refused(self.refused)

        credentials = self.stored()
        if credentials is not None and not credentials.valid:
            if credentials.expired and credentials.refresh_token:
                try:
                    credentials.refresh(Request())
                    self._remember(credentials)
                except RefreshError:
                    # AC 13. A refresh token Google will not honour - revoked at
                    # its end, or expired because the app is in Testing, which
                    # kills every refresh token after seven days. Neither is a
                    # failure to report: it is a grant that has to be asked for
                    # again, so fall through to the flow rather than raising.
                    credentials = None
            else:
                credentials = None

        if credentials is None:
            credentials = self._granted(announce)

        # `cache_discovery=False` because the default writes a discovery
        # document into an `oauth2client` cache directory that this project
        # does not own and did not ask for - and it warns on every build when
        # `oauth2client` is absent, which it is.
        self._service = build(
            "gmail", "v1", credentials=credentials, cache_discovery=False
        )
        return self._service

    def _granted(self, announce=None):  # noqa: ANN001
        """The browser flow, once (AC 4 to AC 10).

        `announce` is called *before* the browser opens, not after, which is
        AC 5: the user is told which service is asking and what it will be able
        to read while there is still time to read it.
        """
        from google_auth_oauthlib.flow import InstalledAppFlow

        if not self.interactive:
            # AC 37. A redirected or piped run has nobody to look at a browser,
            # and `run_local_server` opens one by default and will not ask.
            raise Refused(
                "Gmail needs permission, and this run is not a terminal - "
                "run axiom at a console once to grant it"
            )

        if announce is not None:
            announce()

        flow = InstalledAppFlow.from_client_config(
            {
                "installed": {
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                }
            },
            [SCOPE],
        )
        try:
            credentials = flow.run_local_server(
                # An ephemeral port rather than the library's 8080, which is
                # ordinary enough to already be in use. A Desktop-app client
                # accepts any loopback port, so nothing has to be registered.
                port=0,
                # Axiom has already said this in its own voice, through
                # `announce`. The library's message would be a second telling,
                # unstyled, and it prints even when nothing is watching.
                authorization_prompt_message=None,
                # AC 10. Without it the listener waits forever, and a user who
                # closed the tab never gets their session back.
                timeout_seconds=self.timeout,
            )
        except Exception as failed:  # noqa: BLE001
            # AC 5, AC 6, AC 10 all land here and all mean the same thing to
            # the session: no permission, still running. Recorded so the next
            # call in the same turn does not reopen the browser.
            self.refused = _why(failed)
            raise Refused(self.refused) from failed

        self._remember(credentials)
        self.refused = ""
        return credentials


class Refused(Exception):
    """Permission was not obtained, and here is what to tell the user.

    Carries a sentence, never a token or a URL with one in it (AC 29, AC 30).
    """


def _why(failed: Exception) -> str:
    """A failed grant as one line, with nothing sensitive in it.

    **The exception's text is not passed through.** `oauthlib` puts the full
    redirect it received into some of its errors, and that redirect carries the
    authorization code. Naming the kind of failure keeps the token out of every
    place the message can reach - the tool line, a log, the model's context.
    """
    name = type(failed).__name__
    if name == "WSGITimeoutError":
        return "the browser was not answered in time, so Gmail was not granted"
    if "access_denied" in str(failed) or name == "AccessDeniedError":
        return "permission was declined, so Gmail is not available this session"
    return f"the permission flow did not complete ({name}), so Gmail is not available"


def from_environment(interactive: bool = True) -> Mailbox:
    """The session's mailbox, as the environment describes it.

    Always returns one. A run with nothing configured gets a `Mailbox` that
    reports why rather than a `None` every caller would have to test for -
    which is what makes AC 1 a filter rather than a special case.
    """
    named = os.environ.get(TOKEN_FILE, "").strip()
    return Mailbox(
        client_id=os.environ.get(CLIENT_ID, "").strip(),
        client_secret=os.environ.get(CLIENT_SECRET, "").strip(),
        token_file=Path(named).expanduser() if named else DEFAULT_TOKEN_FILE,
        interactive=interactive,
    )

# Assumptions

Standing inputs. May change between iterations — when one does, say so in that cycle's Observe.

## The route

- **The Gmail API directly, not Google's MCP server.** `gmailmcp.googleapis.com` is gated
  behind the Workspace Developer Preview; the API is not. This story adds a tool native to
  axiom, in `tools.py`'s sense — not a `ServerSpec`, not anything in `servers.py`.
- **`google-auth-oauthlib`'s `InstalledAppFlow.run_local_server()` does the browser flow.**
  Discovery, the loopback listener, the browser open, catching the code, caching the token —
  all inside the library. Axiom writes none of it. Reuse before build.
- Three dependencies: `google-api-python-client`, `google-auth-oauthlib`,
  `google-auth-httplib2`.
- **Google has no API key for this.** Mail is private user data; a key reaches only public
  APIs. OAuth is not avoidable and is not a design choice to revisit.

## The scope

- **`https://www.googleapis.com/auth/gmail.readonly`, and nothing else.** The scope that
  would permit sending or deleting is never requested (AC 28), so a model that improvises
  its way to `send` gets a 403 from Google rather than a sent message.
- Nothing axiom offers can send, delete, archive, or modify (AC 27).

## The credentials

- Client ID and secret come from **the environment**, following axiom's existing
  `AXIOM_*` convention — not a `client_secret.json` committed anywhere, and not a path
  frozen at install time.
- The token cache lives **outside the repository** and is readable only by the user
  (AC 14). `.axiom/` is relative to the working directory and is therefore not a
  candidate.
- **No test needs a real credential.** The flow is stubbed and the Gmail client is a fake
  everywhere except the manual pass.

## The 7-day expiry

- Kaushik's app is **External, in Testing**, so Google expires every refresh token after
  exactly 7 days. This is accepted, not a defect.
- It makes **AC 12** (silent renewal) unprovable past day 7 and **AC 13** (cannot renew,
  offer the flow again) easy to reach. Say which is which in the log; never let the
  expiry be reported as a bug.

## Rules that hold here

- **No test builds a `prompt_toolkit` session** — not a `PromptSession`, not a
  `create_pipe_input`, not a key processor. Nineteen did and took this machine down twice.
- **Break a criterion before claiming it.** Remove the fix, watch the right test go red,
  put it back.
- **Commit before you break.** `git checkout --` takes uncommitted work with it.
- **Watch the wall clock, not just the green.** A break that speeds the suite up has made
  it do less. Record passed / deselected / seconds every cycle.
- **Master is hook-protected.** Work on a branch; the merge is a PR.
- A live model is only ever asked for non-destructive work, with its working directory in
  `C:/Projects/.tmp/axiom-tool-sandbox`.

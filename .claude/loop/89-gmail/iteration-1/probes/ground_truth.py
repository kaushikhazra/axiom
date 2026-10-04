"""What Gmail actually returns for each folder operator a model might guess.

Not a test and not part of axiom. It asks Google the same three ways, straight
through the API with the grant axiom already holds, so a query axiom relayed can
be checked against the mailbox rather than against the answer.

The column that matters is `INBOX`: Gmail accepts a great deal of syntax and
silently ignores the part it does not recognise, so a query can return ten
plausible messages and still not be a folder filter at all.
"""

import sys
from pathlib import Path

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

# Subject lines carry emoji and a piped stdout on Windows is cp1252, which has
# no byte for them. Anything that raises here stops the listing halfway and the
# comparison this script exists for never prints.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

SCOPE = "https://www.googleapis.com/auth/gmail.readonly"
TOKEN = Path("C:/Users/hazra/.axiom/gmail-token.json")
HOW_MANY = 12


def rows(service, **listing):
    found = (
        service.users()
        .messages()
        .list(userId="me", maxResults=HOW_MANY, **listing)
        .execute()
    )
    for stub in found.get("messages", []):
        full = (
            service.users()
            .messages()
            .get(
                userId="me",
                id=stub["id"],
                format="metadata",
                metadataHeaders=["Subject", "From", "Date"],
            )
            .execute()
        )
        headers = {h["name"]: h["value"] for h in full["payload"].get("headers", [])}
        yield (
            stub["id"],
            "INBOX" if "INBOX" in full.get("labelIds", []) else "-----",
            headers.get("Date", "")[:31],
            headers.get("Subject", "")[:52],
        )


def main() -> None:
    creds = Credentials.from_authorized_user_file(str(TOKEN), [SCOPE])
    service = build("gmail", "v1", credentials=creds, cache_discovery=False)

    asked = [
        ("label INBOX (ground truth)", {"labelIds": ["INBOX"]}),
        ("q=in:inbox", {"q": "in:inbox"}),
        ("q=is:inbox", {"q": "is:inbox"}),
        ("q=inbox", {"q": "inbox"}),
    ]
    truth: list[str] = []
    for title, listing in asked:
        print(f"\n== {title}")
        ids = []
        for message_id, label, date, subject in rows(service, **listing):
            ids.append(message_id)
            print(f"  {message_id}  {label}  {date}  {subject}")
        if not truth:
            truth = ids
        else:
            same = ids == truth
            missing = [i for i in truth if i not in ids]
            print(
                f"  -> {'identical to ground truth' if same else 'DIFFERS'}; missing {len(missing)} of {len(truth)}"
            )


if __name__ == "__main__":
    sys.exit(main())

"""Local Gmail OAuth and read-only message retrieval."""

import base64
from datetime import datetime, timezone
from email.utils import parseaddr
from html.parser import HTMLParser
import os
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build


GMAIL_READONLY_SCOPE = "https://www.googleapis.com/auth/gmail.readonly"
SCOPES = [GMAIL_READONLY_SCOPE]
DEFAULT_CREDENTIALS_FILE = Path(__file__).parent / "credentials.json"
DEFAULT_TOKEN_FILE = Path(__file__).parent / "data" / "gmail_token.json"


class _HTMLTextExtractor(HTMLParser):
    """Collect visible text from a small HTML email body."""

    def __init__(self):
        super().__init__()
        self.parts = []

    def handle_data(self, data):
        text = data.strip()
        if text:
            self.parts.append(text)

    def text(self):
        return "\n".join(self.parts)


def credentials_file():
    """Return the OAuth client-secret path without exposing its contents."""
    configured = os.environ.get("GMAIL_CREDENTIALS_FILE")
    return Path(configured).expanduser() if configured else DEFAULT_CREDENTIALS_FILE


def token_file():
    """Return the private local OAuth-token path."""
    configured = os.environ.get("GMAIL_TOKEN_FILE")
    return Path(configured).expanduser() if configured else DEFAULT_TOKEN_FILE


def save_credentials(credentials):
    """Persist OAuth credentials in the ignored local data directory."""
    path = token_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(credentials.to_json(), encoding="utf-8")


def load_credentials():
    """Load and refresh existing Gmail credentials when available."""
    path = token_file()
    if not path.exists():
        return None
    credentials = Credentials.from_authorized_user_file(path, SCOPES)
    if credentials.expired and credentials.refresh_token:
        credentials.refresh(Request())
        save_credentials(credentials)
    return credentials if credentials.valid else None


def connect_gmail():
    """Open Google's OAuth screen and save the granted read-only token."""
    client_file = credentials_file()
    if not client_file.exists():
        raise FileNotFoundError(
            f"Gmail OAuth credentials were not found at {client_file}."
        )
    flow = InstalledAppFlow.from_client_secrets_file(client_file, SCOPES)
    credentials = flow.run_local_server(port=0)
    save_credentials(credentials)
    return credentials


def disconnect_gmail():
    """Remove the local token; authorization can also be revoked at Google."""
    path = token_file()
    if path.exists():
        path.unlink()


def build_gmail_service(credentials=None):
    """Create an authorized Gmail API client."""
    credentials = credentials or load_credentials()
    if credentials is None:
        raise PermissionError("Gmail is not connected.")
    return build("gmail", "v1", credentials=credentials, cache_discovery=False)


def gmail_profile(service):
    """Return the connected account's Gmail profile."""
    return service.users().getProfile(userId="me").execute()


def build_job_email_query(since_date):
    """Build a broad Gmail search whose results are classified locally."""
    formatted_date = since_date.strftime("%Y/%m/%d")
    signals = (
        'subject:application subject:interview subject:offer '
        '"thank you for applying" "application received" '
        '"not moving forward" "not selected" "position has been filled"'
    )
    return f"after:{formatted_date} -hackathon {{{signals}}}"


def list_message_references(service, query):
    """Return all Gmail message references matching a search query."""
    messages = []
    page_token = None
    while True:
        request = service.users().messages().list(
            userId="me",
            q=query,
            maxResults=500,
            pageToken=page_token,
        )
        response = request.execute()
        messages.extend(response.get("messages", []))
        page_token = response.get("nextPageToken")
        if not page_token:
            return messages


def _decode_base64url(data):
    """Decode Gmail's base64url body representation."""
    if not data:
        return ""
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(f"{data}{padding}").decode(
        "utf-8", errors="replace"
    )


def _collect_body_parts(part, plain_parts, html_parts):
    """Walk a Gmail MIME payload and collect readable body parts."""
    mime_type = part.get("mimeType", "")
    data = part.get("body", {}).get("data")
    if data and mime_type == "text/plain":
        plain_parts.append(_decode_base64url(data))
    elif data and mime_type == "text/html":
        html_parts.append(_decode_base64url(data))
    for child in part.get("parts", []):
        _collect_body_parts(child, plain_parts, html_parts)


def extract_message_body(payload):
    """Prefer plain text and fall back to visible HTML email text."""
    plain_parts = []
    html_parts = []
    _collect_body_parts(payload, plain_parts, html_parts)
    if plain_parts:
        return "\n".join(plain_parts)
    if html_parts:
        parser = _HTMLTextExtractor()
        parser.feed("\n".join(html_parts))
        return parser.text()
    return _decode_base64url(payload.get("body", {}).get("data"))


def simplify_message(message):
    """Convert a Gmail API message into fields used by the classifier."""
    payload = message.get("payload", {})
    headers = {
        header.get("name", "").lower(): header.get("value", "")
        for header in payload.get("headers", [])
    }
    timestamp = int(message.get("internalDate", "0")) / 1000
    received = datetime.fromtimestamp(timestamp, tz=timezone.utc)
    sender_name, sender_address = parseaddr(headers.get("from", ""))
    return {
        "message_id": message["id"],
        "thread_id": message.get("threadId", ""),
        "subject": headers.get("subject", ""),
        "sender_name": sender_name,
        "sender_address": sender_address.lower(),
        "received_at": received.isoformat(),
        "received_date": received.date().isoformat(),
        "body": extract_message_body(payload),
        "snippet": message.get("snippet", ""),
    }


def scan_gmail_messages(service, since_date):
    """Retrieve and simplify all candidate job emails since a date."""
    query = build_job_email_query(since_date)
    references = list_message_references(service, query)
    messages = []
    for reference in references:
        full_message = (
            service.users()
            .messages()
            .get(userId="me", id=reference["id"], format="full")
            .execute()
        )
        messages.append(simplify_message(full_message))
    return messages

import asyncio
import base64
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from src.core.config import settings
from src.core.security import decrypt_token


class GmailTool:
    def __init__(self, token_data: dict):
        self.token_data = token_data
        self._client = self._get_client()

    def _get_client(self):
        creds = Credentials(
            token=self.token_data["access_token"],
            refresh_token=self.token_data["refresh_token"],
            token_uri="https://oauth2.googleapis.com/token",
            client_id=settings.CLIENT_ID,
            client_secret=settings.CLIENT_SECRET,
        )

        if creds.expired:
            creds.refresh(Request())

        return build("gmail", "v1", credentials=creds)

    def extract_body(self, payload):
        """Recursively extract plain text body from email payload."""
        if "parts" in payload:
            for part in payload["parts"]:
                if part["mimeType"] == "text/plain":
                    data = part["body"].get("data", "")
                    return base64.urlsafe_b64decode(data).decode(
                        "utf-8", errors="ignore"
                    )
                elif "parts" in part:
                    body = self.extract_body(part)
                    if body:
                        return body
        else:
            data = payload.get("body", {}).get("data", "")
            if data:
                return base64.urlsafe_b64decode(data).decode("utf-8", errors="ignore")
        return ""

    async def read_emails(self, max_results=5, query=""):
        """
        query examples:
          'is:unread'           → unread emails
          'from:someone@x.com'  → from specific sender
          'subject:invoice'     → by subject
          'is:unread label:inbox' → unread inbox
        """
        results = await asyncio.to_thread(
            self._client.users()
            .messages()
            .list(userId="me", maxResults=max_results, q=query)
            .execute
        )

        messages = results.get("messages", [])
        emails = []

        for msg in messages:
            email_data = await asyncio.to_thread(
                self._client.users()
                .messages()
                .get(userId="me", id=msg["id"], format="full")
                .execute
            )

            headers = email_data["payload"]["headers"]
            subject = next(
                (h["value"] for h in headers if h["name"].lower() == "subject"),
                "No Subject",
            )
            sender = next(
                (h["value"] for h in headers if h["name"].lower() == "from"), "Unknown"
            )
            date = next(
                (h["value"] for h in headers if h["name"].lower() == "date"), "Unknown"
            )

            body = self.extract_body(email_data["payload"])
            if body and len(body) > 800:
                body = body[:800] + "..."

            emails.append(
                {
                    "id": msg["id"],
                    "subject": subject,
                    "from": sender,
                    "date": date,
                    "body": body,
                    "snippet": email_data.get("snippet", ""),
                }
            )

        return emails

    async def send_email(
        self, to, subject, body, cc=None, bcc=None, attachment_path=None
    ):
        msg = MIMEMultipart()
        msg["To"] = to
        msg["Subject"] = subject
        if cc:
            msg["Cc"] = cc
        if bcc:
            msg["Bcc"] = bcc

        msg.attach(MIMEText(body, "plain"))

        if attachment_path:
            with open(attachment_path, "rb") as f:
                part = MIMEBase("application", "octet-stream")
                part.set_payload(f.read())
            encoders.encode_base64(part)
            part.add_header(
                "Content-Disposition", f'attachment; filename="{attachment_path}"'
            )
            msg.attach(part)

        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
        result = await asyncio.to_thread(
            self._client.users().messages().send(userId="me", body={"raw": raw}).execute
        )

        print(f"Email sent! Message ID: {result['id']}")
        return result

    async def reply_to_email(self, message_id, reply_body):
        original = await asyncio.to_thread(
            self._client.users()
            .messages()
            .get(userId="me", id=message_id, format="full")
            .execute
        )

        headers = original["payload"]["headers"]
        subject = next(
            (h["value"] for h in headers if h["name"].lower() == "subject"), ""
        )
        reply_to = next(
            (h["value"] for h in headers if h["name"].lower() == "from"), ""
        )
        thread_id = original["threadId"]
        msg_id_header = next(
            (h["value"] for h in headers if h["name"].lower() == "message-id"), ""
        )

        reply = MIMEText(reply_body, "plain")
        reply["To"] = reply_to
        reply["Subject"] = (
            f"Re: {subject}" if not subject.lower().startswith("re:") else subject
        )
        if msg_id_header:
            reply["In-Reply-To"] = msg_id_header
            reply["References"] = msg_id_header

        raw = base64.urlsafe_b64encode(reply.as_bytes()).decode()
        result = await asyncio.to_thread(
            self._client.users()
            .messages()
            .send(userId="me", body={"raw": raw, "threadId": thread_id})
            .execute
        )

        print(f"Reply sent! Message ID: {result['id']}")
        return result

    async def mark_as_read(self, message_id):
        await asyncio.to_thread(
            self._client.users()
            .messages()
            .modify(userId="me", id=message_id, body={"removeLabelIds": ["UNREAD"]})
            .execute
        )
        print(f"Marked as read: {message_id}")

    async def archive_email(self, message_id):
        await asyncio.to_thread(
            self._client.users()
            .messages()
            .modify(userId="me", id=message_id, body={"removeLabelIds": ["INBOX"]})
            .execute
        )
        print(f"Archived: {message_id}")

    async def trash_email(self, message_id):
        await asyncio.to_thread(
            self._client.users().messages().trash(userId="me", id=message_id).execute
        )
        print(f"Trashed: {message_id}")


async def get_gmail_tool(user_id: str) -> GmailTool:
    from src.core.database import async_session_factory
    from src.services.google_oauth import GoogleService, refresh_access_token

    g_serv = GoogleService()
    async with async_session_factory() as session:
        user = await g_serv.get_gmail_user_by_id(user_id, session)
        if not user:
            raise ValueError(f"No Google account found for user {user_id}")

        creds = await refresh_access_token(user, session)
        token_data = {
            "access_token": decrypt_token(creds.token),
            "refresh_token": decrypt_token(creds.refresh_token),
        }
        return GmailTool(token_data=token_data)

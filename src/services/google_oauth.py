import asyncio
import logging
import os

from fastapi import HTTPException
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from sqlalchemy.ext.asyncio.session import AsyncSession
from sqlmodel import select

from src.core.security import decrypt_token, encrypt_token
from src.models.database import GoogleAccount, OAuthSession
from src.core.config import settings

logger = logging.getLogger(__name__)

CLIENT_ID = settings.CLIENT_ID
CLIENT_SECRET = settings.CLIENT_SECRET

SCOPES = [
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.compose",
    "https://www.googleapis.com/auth/gmail.modify",
]

REDIRECT_URI = settings.GOOGLE_REDIRECT_URI


def create_flow() -> Flow:
    flow = Flow.from_client_config(
        {
            "web": {
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
            }
        },
        scopes=SCOPES,
        redirect_uri=REDIRECT_URI,
    )
    return flow


async def refresh_access_token(user, session):
    """Refresh Google OAuth credentials if expired, and auto-encrypt legacy plaintext DB records."""
    raw_access = decrypt_token(user.access_token)
    raw_refresh = decrypt_token(user.refresh_token)

    # Auto-migrate legacy plaintext database records to encrypted Fernet strings
    if (user.access_token and not user.access_token.startswith("gAAAAA")) or (
        user.refresh_token and not user.refresh_token.startswith("gAAAAA")
    ):
        user.access_token = encrypt_token(raw_access)
        user.refresh_token = encrypt_token(raw_refresh)
        await session.commit()
        await session.refresh(user)

    creds = Credentials(
        token=raw_access,
        refresh_token=raw_refresh,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        scopes=user.scope,
    )

    if not creds.valid:
        try:
            await asyncio.to_thread(creds.refresh, Request())

            user.access_token = encrypt_token(creds.token)
            user.token_expiry = (
                creds.expiry.replace(tzinfo=None) if creds.expiry else None
            )

            await session.commit()
            await session.refresh(user)

        except Exception as exc:
            logger.warning("Token refresh failed: %s", exc)
            raise HTTPException(
                status_code=401,
                detail="Re-authentication required",
            )

    return creds


class GoogleService:
    async def create_gmail_user(self, data: dict, session: AsyncSession):
        existing = await self.get_gmail_user_by_id(str(data.get("user_uid")), session)
        if existing:
            existing.access_token = data["access_token"]
            existing.refresh_token = data.get("refresh_token") or existing.refresh_token
            existing.token_expiry = data.get("token_expiry")
            existing.scope = data.get("scope", existing.scope)
            existing.google_email = data.get("google_email", existing.google_email)
            await session.commit()
            return existing

        new_user = GoogleAccount(**data)
        session.add(new_user)
        await session.commit()
        return new_user

    async def get_gmail_user_by_email(self, email: str, session: AsyncSession):
        stmt = select(GoogleAccount).where(GoogleAccount.google_email == email)
        result = await session.execute(stmt)
        return result.scalars().first()

    async def get_gmail_user_by_id(self, id: str, session: AsyncSession):
        import uuid

        try:
            uuid_id = uuid.UUID(id) if isinstance(id, str) else id
        except ValueError:
            uuid_id = id
        stmt = select(GoogleAccount).where(GoogleAccount.user_uid == uuid_id)
        result = await session.execute(stmt)
        return result.scalars().first()

    async def get_code_verifier_state(self, state: str, session: AsyncSession):
        stmt = select(OAuthSession).where(OAuthSession.state == state)
        result = await session.execute(stmt)
        return result.scalars().first()

    async def create_oauth_session(
        self, user_uid: str, state: str, code_verifier: str, session: AsyncSession
    ):
        new_session = OAuthSession(
            user_uid=user_uid, state=state, code_verifier=code_verifier
        )
        session.add(new_session)
        await session.commit()
        return new_session

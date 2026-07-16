import logging
import asyncio
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from fastapi import HTTPException
from google_auth_oauthlib.flow import Flow
from sqlmodel import select
from sqlalchemy.ext.asyncio.session import AsyncSession
from src.config import configure
from src.models.database import User, GoogleAccount, OAuthSession

logger = logging.getLogger(__name__)

CLIENT_ID = configure.CLIENT_ID
CLIENT_SECRET = configure.CLIENT_SECRET

SCOPES = [
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.compose",
    "https://www.googleapis.com/auth/gmail.modify",
]

REDIRECT_URI = configure.GOOGLE_REDIRECT_URI


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
    """Refresh Google OAuth credentials if expired."""
    creds = Credentials(
        token=user.access_token,
        refresh_token=user.refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        scopes=user.scope,
    )

    if not creds.valid:
        try:
            await asyncio.to_thread(creds.refresh, Request())

            user.access_token = creds.token
            user.token_expiry = creds.expiry.replace(tzinfo=None) if creds.expiry else None

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

    saas_verifier = None # wait, remove
    async def create_oauth_session(
        self, user_uid: str, state: str, code_verifier: str, session: AsyncSession
    ):
        new_session = OAuthSession(
            user_uid=user_uid, state=state, code_verifier=code_verifier
        )
        session.add(new_session)
        await session.commit()
        return new_session

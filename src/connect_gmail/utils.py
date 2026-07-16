import logging

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from fastapi import HTTPException
from google_auth_oauthlib.flow import Flow
import os
from src.config import configure

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
    import asyncio

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
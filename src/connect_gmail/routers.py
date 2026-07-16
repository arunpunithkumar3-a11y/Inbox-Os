import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio.session import AsyncSession
from src.db.main import get_session
from googleapiclient.discovery import build
from src.connect_gmail.utils import create_flow, refresh_access_token
from src.connect_gmail.service import GoogleService
from src.auth.dependency import verify_token, verify__token

logger = logging.getLogger(__name__)

google_router = APIRouter()
g_serv = GoogleService()


@google_router.get("/g/login")
async def login(
    redirect_uri: str = "/",
    session: AsyncSession = Depends(get_session),
    token_details=Depends(verify__token),
):
    flow = create_flow()

    oauth_state = str(uuid.uuid4())
    auth_url, state = flow.authorization_url(
        state=f"{oauth_state}|{redirect_uri}",
        prompt="consent",
        access_type="offline",
        include_granted_scopes="true",
        code_challenge_method="S256",
    )

    await g_serv.create_oauth_session(
        token_details["user_data"]["user_id"],
        oauth_state,
        flow.code_verifier,
        session,
    )

    return RedirectResponse(auth_url)


@google_router.get("/g/callback")
async def callback(
    code: str,
    state: str,
    session: AsyncSession = Depends(get_session),
):
    import asyncio

    state_parts = state.split("|", 1)
    oauth_state = state_parts[0]
    redirect_uri = state_parts[1] if len(state_parts) > 1 else "/"

    oauth_session = await g_serv.get_code_verifier_state(state=oauth_state, session=session)

    if not oauth_session:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid OAuth state")

    flow = create_flow()

    try:
        await asyncio.to_thread(
            flow.fetch_token,
            code=code,
            code_verifier=oauth_session.code_verifier,
        )
    except Exception as exc:
        logger.error("Failed to fetch Google OAuth token: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to retrieve credentials from Google. Please try again."
        )

    credentials = flow.credentials

    try:
        oauth2_client = build("oauth2", "v2", credentials=credentials)
        user_info = await asyncio.to_thread(oauth2_client.userinfo().get().execute)
    except Exception as exc:
        logger.error("Failed to fetch Google user info: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to retrieve user details from Google."
        )

    email = user_info.get("email")

    if not email:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unable to fetch email from Google")

    data = {
        "google_email": email,
        "user_uid": oauth_session.user_uid,
        "access_token": credentials.token,
        "refresh_token": credentials.refresh_token,
        "token_expiry": credentials.expiry.replace(tzinfo=None) if credentials.expiry else None,
        "scope": credentials.scopes,
    }

    await g_serv.create_gmail_user(data, session)

    return RedirectResponse(redirect_uri)


@google_router.get("/g/user/{id}", status_code=status.HTTP_200_OK)
async def get_gmail_user(id: str, session: AsyncSession = Depends(get_session)):
    user = await g_serv.get_gmail_user_by_id(id, session)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"message": "User not found"},
        )

    return user
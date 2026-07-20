import asyncio
import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import RedirectResponse
from googleapiclient.discovery import build
from sqlalchemy.ext.asyncio.session import AsyncSession

from src.core.database import get_session
from src.core.security import encrypt_token, verify__token, verify_token
from src.services.google_oauth import GoogleService, create_flow

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
    state_parts = state.split("|", 1)
    oauth_state = state_parts[0]
    redirect_uri = state_parts[1] if len(state_parts) > 1 else "/"

    oauth_session = await g_serv.get_code_verifier_state(
        state=oauth_state, session=session
    )

    if not oauth_session:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid OAuth state"
        )

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
            detail="Failed to retrieve credentials from Google. Please try again.",
        )

    credentials = flow.credentials

    try:
        oauth2_client = build("oauth2", "v2", credentials=credentials)
        user_info = await asyncio.to_thread(oauth2_client.userinfo().get().execute)
    except Exception as exc:
        logger.error("Failed to fetch Google user info: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to retrieve user details from Google.",
        )

    email = user_info.get("email")

    if not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unable to fetch email from Google",
        )

    existing_user = await g_serv.get_gmail_user_by_id(oauth_session.user_uid, session)
    if not credentials.refresh_token and (
        not existing_user or not existing_user.refresh_token
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Offline access grant missing refresh token. Please re-authenticate and grant full access.",
        )

    data = {
        "google_email": email,
        "user_uid": oauth_session.user_uid,
        "access_token": encrypt_token(credentials.token),
        "refresh_token": encrypt_token(credentials.refresh_token)
        if credentials.refresh_token
        else None,
        "token_expiry": credentials.expiry.replace(tzinfo=None)
        if credentials.expiry
        else None,
        "scope": credentials.scopes,
    }

    await g_serv.create_gmail_user(data, session)

    return RedirectResponse(redirect_uri)


@google_router.get("/g/user/{id}", status_code=status.HTTP_200_OK)
async def get_gmail_user(
    id: str,
    session: AsyncSession = Depends(get_session),
    token_details=Depends(verify_token),
):
    logged_in_uid = token_details["user_data"]["user_id"]
    if logged_in_uid != id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail={"message": "Access denied"}
        )

    user = await g_serv.get_gmail_user_by_id(id, session)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"message": "User not found"},
        )

    return {
        "google_email": user.google_email,
        "created_at": user.created_at,
    }

import logging
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio.session import AsyncSession

from core.database import get_session
from core.redis import add_jti_to_blacklist
from core.security import create_access_token, verify_password, verify_refresh_token
from models.auth import UserLogin, UserSignup
from services.auth import UserService

logger = logging.getLogger(__name__)

user_serv = UserService()
auth_router = APIRouter()

REFRESH_TOKEN_EXPIRY_DAYS = 30


@auth_router.post("/signup", status_code=status.HTTP_201_CREATED)
async def user_signup(data: UserSignup, session: AsyncSession = Depends(get_session)):
    email = data.email
    if await user_serv.user_exists(email, session):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"message": "User with this email already exists"},
        )
    await user_serv.create_user(data, session)
    return {"message": "Account created successfully"}


@auth_router.post("/login", status_code=status.HTTP_200_OK)
async def user_login(
    response: Response,
    data: UserLogin,
    session: AsyncSession = Depends(get_session),
):
    user = await user_serv.get_user_by_email(data.email, session)

    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"message": "Invalid email or password"},
        )

    access_token = create_access_token(
        data={"email": user.email, "user_id": str(user.uid)}
    )

    refresh_token = create_access_token(
        data={"email": user.email, "user_id": str(user.uid)},
        refresh=True,
        expire=timedelta(days=REFRESH_TOKEN_EXPIRY_DAYS),
    )

    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=True,
        samesite="lax",
        path="/",
    )
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=True,
        samesite="lax",
        path="/",
    )

    return {"access_token": access_token, "refresh_token": refresh_token}


@auth_router.post("/logout/{jti}", status_code=status.HTTP_200_OK)
async def user_logout(jti: str, response: Response = None):
    if not jti:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"message": "Please provide a valid token identifier"},
        )
    await add_jti_to_blacklist(jti)
    if response:
        response.delete_cookie(key="access_token", path="/")
        response.delete_cookie(key="refresh_token", path="/")
    return {"message": "Logout successful"}


@auth_router.api_route("/refresh_token", methods=["GET", "POST"])
async def get_new_access_token(
    response: Response,
    token_data: dict = Depends(verify_refresh_token),
):
    user_payload = token_data["user_data"]
    old_jti = token_data.get("jti")
    if old_jti:
        await add_jti_to_blacklist(old_jti)

    new_access_token = create_access_token(data=user_payload)
    new_refresh_token = create_access_token(
        data=user_payload,
        refresh=True,
        expire=timedelta(days=REFRESH_TOKEN_EXPIRY_DAYS),
    )

    response.set_cookie(
        key="access_token",
        value=new_access_token,
        httponly=True,
        secure=True,
        samesite="lax",
        path="/",
    )
    response.set_cookie(
        key="refresh_token",
        value=new_refresh_token,
        httponly=True,
        secure=True,
        samesite="lax",
        path="/",
    )

    return {"access_token": new_access_token, "refresh_token": new_refresh_token}

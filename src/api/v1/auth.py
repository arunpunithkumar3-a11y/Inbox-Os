import logging
from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status, Response
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio.session import AsyncSession
from src.services.auth import UserService
from src.models.auth import UserLogin, UserSignup
from src.core.security import verify_password, create_access_token, verify_refresh_token
from src.core.database import get_session
from src.core.redis import add_jti_to_blacklist

logger = logging.getLogger(__name__)

user_serv = UserService()
auth_router = APIRouter()

REFRESH_TOKEN_EXPIRY_DAYS = 2


@auth_router.post("/signup", status_code=status.HTTP_201_CREATED)
async def user_signup(
    data: UserSignup, session: AsyncSession = Depends(get_session)
):
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

    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=True,
        samesite="lax",
        path="/",
    )

    refresh_token = create_access_token(
        data={"email": user.email, "user_id": str(user.uid)},
        refresh=True,
        expire=timedelta(days=REFRESH_TOKEN_EXPIRY_DAYS),
    )

    return {"access_token": access_token, "refresh_token": refresh_token}


@auth_router.post("/logout/{jti}", status_code=status.HTTP_200_OK)
async def user_logout(jti: str):
    if not jti:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"message": "Please provide a valid token identifier"},
        )
    await add_jti_to_blacklist(jti)
    return {"message": "Logout successful"}


@auth_router.get("/refresh_token")
async def get_new_access_token(
    token_data: dict = Depends(verify_refresh_token)
):
    new_access_token = create_access_token(
        data=token_data["user_data"]
    )
    return JSONResponse(content={"access_token": new_access_token})

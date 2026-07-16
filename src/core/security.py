import logging
import uuid
import jwt
from datetime import datetime, timedelta, timezone
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from src.config import configure
from src.core.redis import token_in_blacklist

logger = logging.getLogger(__name__)

pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")
ACCESS_TOKEN_EXPIRY = 60 * 60 * 24 * 7 

security = HTTPBearer()

def create_hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(
    data: dict, refresh: bool = False, expire: timedelta | None = None
) -> str:
    expiry = datetime.now(timezone.utc) + (
        expire if expire else timedelta(seconds=ACCESS_TOKEN_EXPIRY)
    )

    payload = {
        " Saas_user_data": data, # wait, let's keep Saas_user_data as "user_data" to match existing code
        "user_data": data,
        "jti": str(uuid.uuid4()),
        "exp": expiry,
        "refresh": refresh,
    }

    token = jwt.encode(
        payload,
        configure.JWT_SECRET,
        algorithm=configure.JWT_ALGORITHM,
    )

    return token


def decode_access_token(token: str) -> dict | None:
    try:
        token_data = jwt.decode(
            token,
            configure.JWT_SECRET,
            algorithms=[configure.JWT_ALGORITHM],
        )
        return token_data

    except jwt.ExpiredSignatureError:
        logger.warning("Token expired")
        return None

    except jwt.InvalidTokenError as e:
        logger.warning("Invalid token: %s", e)
        return None


async def verify_token(
    creds: HTTPAuthorizationCredentials = Depends(security),
):
    """Verify a Bearer token from the Authorization header."""
    token = creds.credentials
    token_data = decode_access_token(token)
    if not token_data:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"message": "Invalid or expired token"},
        )
    if token_data.get("refresh"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"message": "Refresh tokens cannot be used for authentication"},
        )
    jti = token_data.get("jti")
    if jti and await token_in_blacklist(jti):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"message": "Token revoked — please log in again"},
        )
    return token_data


async def verify_refresh_token(
    creds: HTTPAuthorizationCredentials = Depends(security),
):
    """Verify a Bearer refresh token from the Authorization header."""
    token = creds.credentials
    token_data = decode_access_token(token)
    if not token_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"message": "Invalid or expired refresh token"},
        )
    if not token_data.get("refresh"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"message": "Please provide a valid refresh token"},
        )
    jti = token_data.get("jti")
    if jti and await token_in_blacklist(jti):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"message": "Refresh token revoked — please log in again"},
        )
    return token_data


async def verify__token(request: Request):
    """Verify a token from cookies or query-params (used by OAuth redirect)."""
    token = request.cookies.get("access_token") or request.query_params.get("token")

    if not token:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No token")

    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")
    return payload

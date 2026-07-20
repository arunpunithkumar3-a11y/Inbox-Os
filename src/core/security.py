import logging
import uuid
from datetime import datetime, timedelta, timezone

import jwt
from cryptography.fernet import Fernet
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from passlib.context import CryptContext

from src.core.config import settings
from src.core.redis import token_in_blacklist

logger = logging.getLogger(__name__)

pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")
ACCESS_TOKEN_EXPIRY = 3600
import base64
import hashlib


def _get_fernet_key(secret: str) -> bytes:
    raw_secret = (secret or "inbox-os-default-secret-key-32-bytes").encode("utf-8")
    hashed = hashlib.sha256(raw_secret).digest()
    return base64.urlsafe_b64encode(hashed)


key = _get_fernet_key(settings.SECRET_KEY)
helper = Fernet(key)
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
        "user_data": data,
        "jti": str(uuid.uuid4()),
        "exp": expiry,
        "refresh": refresh,
    }

    token = jwt.encode(
        payload,
        settings.JWT_SECRET,
        algorithm=settings.JWT_ALGORITHM,
    )

    return token


def decode_access_token(token: str) -> dict | None:
    try:
        token_data = jwt.decode(
            token,
            settings.JWT_SECRET,
            algorithms=[settings.JWT_ALGORITHM],
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
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token"
        )
    return payload


def encrypt_token(token: str) -> str:
    if not token:
        return token
    try:
        return helper.encrypt(token.encode()).decode()
    except Exception as e:
        logger.error(f"Token encryption failed{e}")
        return token


def decrypt_token(encrypted_token: str) -> str:
    if not encrypted_token:
        return encrypted_token
    # Fernet ciphertext always starts with the 'gAAAAA' base64 header.
    # If it does not start with 'gAAAAA', it is a legacy unencrypted plaintext token.
    if not encrypted_token.startswith("gAAAAA"):
        return encrypted_token
    try:
        return helper.decrypt(encrypted_token.encode()).decode()
    except Exception as e:
        logger.warning(f"Token decryption failed: {e}")
        return encrypted_token

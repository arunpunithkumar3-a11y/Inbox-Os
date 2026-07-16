import logging

from passlib.context import CryptContext
import jwt
from datetime import datetime, timedelta, timezone
import uuid
from src.config import configure

logger = logging.getLogger(__name__)

pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")
ACCESS_TOKEN_EXPIRY = 60 * 60 * 24 * 7 

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

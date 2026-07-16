import logging

from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi import Depends, HTTPException, status, Request
from src.auth.utils import decode_access_token
from src.db.redis import token_in_blacklist



security = HTTPBearer()


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
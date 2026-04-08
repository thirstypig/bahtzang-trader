from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Cookie, HTTPException, status
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token

from app.config import settings

ALGORITHM = "HS256"
TOKEN_EXPIRE_DAYS = 7


def verify_google_token(token: str) -> dict:
    """
    Verify a Google ID token and return the user info payload.
    Raises HTTPException if the token is invalid or the email is not allowed.
    """
    try:
        payload = id_token.verify_oauth2_token(
            token,
            google_requests.Request(),
            settings.GOOGLE_CLIENT_ID,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid Google token: {e}",
        )

    email = payload.get("email", "")
    if email != settings.ALLOWED_EMAIL:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account is not authorized to access this application",
        )

    return {
        "email": email,
        "name": payload.get("name", ""),
        "picture": payload.get("picture", ""),
    }


def create_jwt(user_info: dict) -> str:
    """Create a signed JWT containing the user's info."""
    payload = {
        **user_info,
        "exp": datetime.now(timezone.utc) + timedelta(days=TOKEN_EXPIRE_DAYS),
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=ALGORITHM)


def decode_jwt(token: str) -> dict:
    """Decode and verify a JWT. Raises HTTPException on failure."""
    try:
        return jwt.decode(token, settings.JWT_SECRET, algorithms=[ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired — please sign in again",
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid session token",
        )


def require_auth(session: str | None = Cookie(None)) -> dict:
    """
    FastAPI dependency that extracts and verifies the JWT from the
    'session' cookie. Returns the decoded user payload or raises 401.
    """
    if not session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    return decode_jwt(session)

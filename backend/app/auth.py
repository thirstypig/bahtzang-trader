import logging

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import settings

logger = logging.getLogger(__name__)

bearer_scheme = HTTPBearer()


def require_auth(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> dict:
    """
    Verify the Supabase access token from the Authorization header.
    Checks the JWT signature and restricts access to ALLOWED_EMAIL.
    """
    token = credentials.credentials
    logger.info("Auth attempt — token length: %d, starts: %s...", len(token), token[:20])

    try:
        payload = jwt.decode(
            token,
            settings.SUPABASE_JWT_SECRET,
            algorithms=["HS256"],
            audience="authenticated",
        )
    except jwt.ExpiredSignatureError:
        logger.warning("Token expired")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired — please sign in again",
        )
    except jwt.InvalidAudienceError as e:
        logger.warning("Audience mismatch: %s", e)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token audience error: {e}",
        )
    except jwt.InvalidSignatureError:
        logger.warning("Signature verification failed — check SUPABASE_JWT_SECRET")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token signature invalid — JWT secret may be wrong",
        )
    except jwt.DecodeError as e:
        logger.warning("Token decode error: %s", e)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token decode error: {e}",
        )
    except jwt.InvalidTokenError as e:
        logger.warning("Invalid token: %s — %s", type(e).__name__, e)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token ({type(e).__name__}): {e}",
        )

    email = payload.get("email", "")
    logger.info("Token valid — email: %s", email)

    if email != settings.ALLOWED_EMAIL:
        logger.warning("Unauthorized email: %s (allowed: %s)", email, settings.ALLOWED_EMAIL)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account is not authorized",
        )

    user_meta = payload.get("user_metadata", {})
    return {
        "id": payload.get("sub"),
        "email": email,
        "name": user_meta.get("full_name", ""),
        "picture": user_meta.get("avatar_url", ""),
    }

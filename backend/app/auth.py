import logging

import jwt
from jwt import PyJWKClient
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import settings

logger = logging.getLogger(__name__)

bearer_scheme = HTTPBearer()

# Supabase publishes its signing keys at this well-known endpoint.
# PyJWKClient fetches and caches the public keys automatically.
_jwks_url = f"{settings.SUPABASE_URL}/auth/v1/.well-known/jwks.json"
_jwks_client = PyJWKClient(_jwks_url)


def require_auth(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> dict:
    """
    Verify the Supabase access token from the Authorization header.
    Fetches the public key from Supabase's JWKS endpoint to verify ES256 tokens.
    Restricts access to ALLOWED_EMAIL.
    """
    token = credentials.credentials

    try:
        # Get the signing key that matches the token's `kid` header
        signing_key = _jwks_client.get_signing_key_from_jwt(token)

        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=["ES256"],
            audience="authenticated",
        )
    except jwt.ExpiredSignatureError:
        logger.warning("Token expired")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired — please sign in again",
        )
    except jwt.InvalidTokenError as e:
        logger.warning("Token verification failed: %s — %s", type(e).__name__, e)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        )
    except Exception as e:
        logger.error("Unexpected auth error: %s — %s", type(e).__name__, e)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed",
        )

    email = payload.get("email", "")
    logger.info("Authenticated: %s", email)

    if email != settings.ALLOWED_EMAIL:
        logger.warning("Unauthorized email: %s", email)
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

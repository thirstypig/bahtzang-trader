import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import settings

bearer_scheme = HTTPBearer()


def require_auth(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> dict:
    """
    Verify the Supabase access token from the Authorization header.
    Checks the JWT signature and restricts access to ALLOWED_EMAIL.
    """
    token = credentials.credentials

    try:
        payload = jwt.decode(
            token,
            settings.SUPABASE_JWT_SECRET,
            algorithms=["HS256"],
            audience="authenticated",
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired — please sign in again",
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        )

    email = payload.get("email", "")
    if email != settings.ALLOWED_EMAIL:
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

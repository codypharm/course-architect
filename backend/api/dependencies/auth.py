"""FastAPI dependency for verifying Clerk-issued JWTs.

Usage:
    from api.dependencies.auth import get_current_user_id

    @router.post("/courses")
    async def start_course(
        ...,
        user_id: str = Depends(get_current_user_id),
    ):
        ...

CLERK_JWKS_URL must be set in the environment. Find it in:
  Clerk Dashboard → API Keys → Advanced → JWKS URL
"""
import os

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient, decode
from jwt import exceptions as jwt_exc

_JWKS_URL = os.environ.get("CLERK_JWKS_URL", "")

# PyJWKClient fetches and caches Clerk's public keys from the JWKS endpoint.
# cache_keys=True keeps them in memory so we don't hit the JWKS URL on every request.
_jwks_client: PyJWKClient | None = PyJWKClient(_JWKS_URL, cache_keys=True) if _JWKS_URL else None

_bearer = HTTPBearer()


def get_current_user_id(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
) -> str:
    """Verify the Clerk JWT in the Authorization header and return the Clerk user ID (sub claim).

    Raises 401 if the token is missing, expired, or invalid.
    Raises 503 if CLERK_JWKS_URL is not configured.
    """
    if _jwks_client is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Auth not configured — set CLERK_JWKS_URL",
        )

    token = credentials.credentials
    try:
        signing_key = _jwks_client.get_signing_key_from_jwt(token)
        payload = decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            options={"verify_exp": True},
        )
    except jwt_exc.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired")
    except jwt_exc.PyJWTError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Invalid token: {exc}")

    user_id: str | None = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token has no subject")
    return user_id

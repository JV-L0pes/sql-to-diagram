import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from src.identity.infrastructure.jwt_service import AccessTokenClaims, JwtService
from src.identity.infrastructure.revoked_access_token_repository import (
    RevokedAccessTokenRepository,
)
from src.shared_kernel.db import get_db
from src.shared_kernel.settings import get_settings

_security = HTTPBearer()


def get_current_claims(
    credentials: HTTPAuthorizationCredentials = Depends(_security),  # noqa: B008
    db: Session = Depends(get_db),  # noqa: B008
) -> AccessTokenClaims:
    settings = get_settings()
    jwt_service = JwtService(secret=settings.jwt_secret)
    try:
        claims = jwt_service.decode_access_token(credentials.credentials)
    except jwt.InvalidTokenError as exc:
        raise HTTPException(status_code=401, detail="Invalid or expired access token") from exc
    if RevokedAccessTokenRepository(db).is_revoked(claims.jti):
        raise HTTPException(status_code=401, detail="Token has been revoked")
    return claims


def get_current_user(claims: AccessTokenClaims = Depends(get_current_claims)) -> str:  # noqa: B008
    return claims.user_id

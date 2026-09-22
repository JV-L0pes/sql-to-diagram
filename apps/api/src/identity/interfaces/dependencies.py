from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
import jwt

from src.identity.infrastructure.jwt_service import JwtService
from src.shared_kernel.settings import get_settings

_security = HTTPBearer()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_security),
) -> str:
    settings = get_settings()
    jwt_service = JwtService(secret=settings.jwt_secret)
    try:
        return jwt_service.decode_access_token(credentials.credentials)
    except jwt.InvalidTokenError as exc:
        raise HTTPException(status_code=401, detail="Invalid or expired access token") from exc

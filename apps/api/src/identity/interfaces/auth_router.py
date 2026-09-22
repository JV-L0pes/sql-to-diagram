from fastapi import APIRouter, Depends, Response
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from src.identity.application.authenticate_user import AuthenticateUser
from src.identity.application.logout import Logout
from src.identity.application.refresh_access_token import RefreshAccessToken
from src.identity.application.register_user import RegisterUser
from src.identity.domain.errors import (
    EmailAlreadyRegisteredError,
    InvalidCredentialsError,
    InvalidRefreshTokenError,
)
from src.identity.infrastructure.jwt_service import JwtService
from src.identity.infrastructure.password_hasher import PasswordHasher
from src.identity.infrastructure.refresh_token_repository import RefreshTokenRepository
from src.identity.infrastructure.user_repository import UserRepository
from src.identity.interfaces.schemas import (
    LoginRequest,
    LogoutRequest,
    RefreshRequest,
    RegisterRequest,
    RegisterResponse,
    TokenResponse,
)
from src.shared_kernel.db import get_db
from src.shared_kernel.errors import error_body
from src.shared_kernel.settings import get_settings

router = APIRouter(prefix="/api/auth", tags=["identity"])


def _jwt_service() -> JwtService:
    return JwtService(secret=get_settings().jwt_secret)


@router.post("/register", status_code=201, response_model=RegisterResponse)
def register(request: RegisterRequest, db: Session = Depends(get_db)):
    use_case = RegisterUser(UserRepository(db), PasswordHasher())
    try:
        user = use_case.execute(request.email, request.password)
    except EmailAlreadyRegisteredError as exc:
        return JSONResponse(status_code=409, content=error_body("email_already_registered", str(exc)))
    return RegisterResponse(id=user.id, email=user.email)


@router.post("/login", response_model=TokenResponse)
def login(request: LoginRequest, db: Session = Depends(get_db)):
    use_case = AuthenticateUser(UserRepository(db), PasswordHasher(), _jwt_service(), RefreshTokenRepository(db))
    try:
        tokens = use_case.execute(request.email, request.password)
    except InvalidCredentialsError as exc:
        return JSONResponse(status_code=401, content=error_body("invalid_credentials", str(exc)))
    return TokenResponse(access_token=tokens.access_token, refresh_token=tokens.refresh_token)


@router.post("/refresh", response_model=TokenResponse)
def refresh(request: RefreshRequest, db: Session = Depends(get_db)):
    use_case = RefreshAccessToken(RefreshTokenRepository(db), _jwt_service())
    try:
        tokens = use_case.execute(request.refresh_token)
    except InvalidRefreshTokenError as exc:
        return JSONResponse(status_code=401, content=error_body("invalid_refresh_token", str(exc)))
    return TokenResponse(access_token=tokens.access_token, refresh_token=tokens.refresh_token)


@router.post("/logout", status_code=204)
def logout(request: LogoutRequest, db: Session = Depends(get_db)):
    Logout(RefreshTokenRepository(db)).execute(request.refresh_token)
    return Response(status_code=204)

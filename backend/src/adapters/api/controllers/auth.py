from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db
from src.adapters.db.repositories.user_repository import SQLAlchemyUserRepository
from src.use_cases.auth import AuthService
from src.adapters.api.schemas.auth import (
    UserRegister, UserLogin, Token, UserResponse,
    OTPRequest, OTPVerify, IdentityVerificationRequest
)
from src.adapters.api.dependencies import get_current_user
from src.adapters.db.models import User

router = APIRouter()

def get_auth_service(db: AsyncSession = Depends(get_db)) -> AuthService:
    user_repo = SQLAlchemyUserRepository(db)
    return AuthService(user_repo)

@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    data: UserRegister,
    service: AuthService = Depends(get_auth_service)
):
    user = await service.register_user(data)
    return user

@router.post("/login", response_model=Token)
async def login(
    data: UserLogin,
    service: AuthService = Depends(get_auth_service)
):
    user, access_token, refresh_token = await service.login_user(
        username=data.username, password=data.password
    )
    return Token(access_token=access_token, refresh_token=refresh_token)

@router.post("/refresh", response_model=Token)
async def refresh(
    refresh_token: str,
    service: AuthService = Depends(get_auth_service)
):
    access_token, new_refresh_token = await service.refresh_session(refresh_token)
    return Token(access_token=access_token, refresh_token=new_refresh_token)

@router.post("/otp/request")
async def request_otp(
    data: OTPRequest,
    service: AuthService = Depends(get_auth_service)
):
    code = await service.send_otp(channel=data.channel, target=data.target)
    # In development, return the code so the client can verify without an SMS gateway integration
    return {
        "message": f"OTP sent successfully to {data.target}",
        "code": code  # Dev-only exposure
    }

@router.post("/otp/verify")
async def verify_otp(
    data: OTPVerify,
    service: AuthService = Depends(get_auth_service)
):
    success = await service.verify_otp(target=data.target, code=data.code)
    return {"verified": success}

@router.post("/kyc/verify", response_model=UserResponse)
async def verify_kyc(
    data: IdentityVerificationRequest,
    current_user: User = Depends(get_current_user),
    service: AuthService = Depends(get_auth_service)
):
    updated_user = await service.verify_identity(str(current_user.id), data)
    return updated_user

@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    return current_user

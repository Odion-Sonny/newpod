import random
import string
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple
from fastapi import HTTPException, status
from src.domain.repositories.user_repository import UserRepositoryInterface
from src.adapters.db.models import User, Wallet, KYCLevel, Role, WalletStatus
from src.core.security import get_password_hash, verify_password, create_access_token, create_refresh_token, decode_token
from src.adapters.api.schemas.auth import UserRegister, IdentityVerificationRequest

# Mock storage for OTP codes during testing/development
# In production, this would use Redis with TTL
MOCK_OTP_STORE = {}

class AuthService:
    def __init__(self, user_repo: UserRepositoryInterface):
        self.user_repo = user_repo

    async def register_user(self, data: UserRegister) -> User:
        # Check email duplicate
        existing_email = await self.user_repo.get_by_email(data.email)
        if existing_email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email is already registered"
            )

        # Check phone duplicate
        existing_phone = await self.user_repo.get_by_phone(data.phone)
        if existing_phone:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Phone number is already registered"
            )

        # Create Role USER if not exists
        user_role = await self.user_repo.get_role_by_name("USER")
        if not user_role:
            user_role = await self.user_repo.create_role("USER")

        # Create user
        hashed_password = get_password_hash(data.password)
        new_user = User(
            email=data.email,
            phone=data.phone,
            password_hash=hashed_password,
            kyc_level=KYCLevel.TIER_0,
            face_verified=False
        )
        new_user.roles.append(user_role)

        # Initialize Wallet
        new_wallet = Wallet(
            balance=0.0,
            currency="NGN",
            status=WalletStatus.ACTIVE
        )
        new_user.wallet = new_wallet

        # Save to DB
        created_user = await self.user_repo.create(new_user)
        return created_user

    async def login_user(self, username: str, password: str) -> Tuple[User, str, str]:
        # Support email or phone login
        user = await self.user_repo.get_by_email(username)
        if not user:
            user = await self.user_repo.get_by_phone(username)

        if not user or not verify_password(password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials"
            )

        access_token = create_access_token(user.id)
        refresh_token = create_refresh_token(user.id)
        return user, access_token, refresh_token

    async def refresh_session(self, refresh_token: str) -> Tuple[str, str]:
        payload = decode_token(refresh_token)
        if not payload or payload.get("type") != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired refresh token"
            )

        user_id = payload.get("sub")
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found"
            )

        new_access = create_access_token(user.id)
        new_refresh = create_refresh_token(user.id)
        return new_access, new_refresh

    async def send_otp(self, channel: str, target: str) -> str:
        # Generate 6 digit code
        code = "".join(random.choices(string.digits, k=6))
        
        # Save to mock store (valid for 5 minutes)
        expiry = datetime.now(timezone.utc) + timedelta(minutes=5)
        MOCK_OTP_STORE[target] = {"code": code, "expiry": expiry}
        
        # In a real environment, send via SMS/Email API here
        # Return code for mock testing/verification
        return code

    async def verify_otp(self, target: str, code: str) -> bool:
        record = MOCK_OTP_STORE.get(target)
        if not record:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="OTP not requested or expired"
            )
        
        if datetime.now(timezone.utc) > record["expiry"]:
            del MOCK_OTP_STORE[target]
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="OTP expired"
            )

        if record["code"] != code:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid OTP code"
            )

        del MOCK_OTP_STORE[target]
        return True

    async def verify_identity(self, user_id: str, request: IdentityVerificationRequest) -> User:
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )

        # Mocking external verification logic for BVN / NIN / Face matching
        if request.bvn:
            # Check BVN format (must be 11 digits)
            if len(request.bvn) != 11 or not request.bvn.isdigit():
                raise HTTPException(status_code=400, detail="BVN must be 11 digits")
            user.bvn_hash = f"hashed_bvn_{request.bvn[-4:]}" # Mock hash

        if request.nin:
            if len(request.nin) != 11 or not request.nin.isdigit():
                raise HTTPException(status_code=400, detail="NIN must be 11 digits")
            user.nin_hash = f"hashed_nin_{request.nin[-4:]}" # Mock hash

        if request.face_image_url:
            user.face_verified = True

        # KYC Level Logic
        # Tier 0: Initial sign-up
        # Tier 1: BVN OR NIN
        # Tier 2: BVN AND NIN
        # Tier 3: BVN AND NIN AND Face Verified
        has_bvn = user.bvn_hash is not None
        has_nin = user.nin_hash is not None
        has_face = user.face_verified

        if has_bvn and has_nin and has_face:
            user.kyc_level = KYCLevel.TIER_3
        elif has_bvn and has_nin:
            user.kyc_level = KYCLevel.TIER_2
        elif has_bvn or has_nin:
            user.kyc_level = KYCLevel.TIER_1
        else:
            user.kyc_level = KYCLevel.TIER_0

        # Boost trust score on verification progress
        if user.kyc_level == KYCLevel.TIER_3:
            user.trust_score = min(user.trust_score + 10.0, 100.0)
        elif user.kyc_level == KYCLevel.TIER_2:
            user.trust_score = min(user.trust_score + 5.0, 100.0)

        updated_user = await self.user_repo.update(user)
        return updated_user

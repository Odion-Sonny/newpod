import uuid
from typing import Optional, List
from pydantic import BaseModel, EmailStr, Field, field_validator
from src.adapters.db.models import KYCLevel

class UserRegister(BaseModel):
    email: EmailStr
    phone: str = Field(..., description="Phone number with country code")
    password: str = Field(..., min_length=8, description="Minimum 8 characters password")

class UserLogin(BaseModel):
    username: str = Field(..., description="Email or phone number")
    password: str

class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"

class TokenPayload(BaseModel):
    sub: str
    type: str
    exp: int

class UserResponse(BaseModel):
    id: uuid.UUID
    email: EmailStr
    phone: str
    kyc_level: KYCLevel
    face_verified: bool
    trust_score: float
    dispute_ratio: float
    fraud_score: float
    roles: List[str] = []

    @field_validator("roles", mode="before")
    @classmethod
    def convert_roles(cls, v):
        if not v:
            return []
        if isinstance(v, list) and len(v) > 0 and not isinstance(v[0], str):
            return [role.name for role in v]
        return v

    model_config = {
        "from_attributes": True
    }

class OTPRequest(BaseModel):
    channel: str = Field(..., pattern="^(email|sms)$")
    target: str

class OTPVerify(BaseModel):
    target: str
    code: str

class IdentityVerificationRequest(BaseModel):
    bvn: Optional[str] = Field(None, min_length=11, max_length=11, description="11-digit Bank Verification Number")
    nin: Optional[str] = Field(None, min_length=11, max_length=11, description="11-digit National Identification Number")
    face_image_url: Optional[str] = Field(None, description="URL of user selfie for face matching")

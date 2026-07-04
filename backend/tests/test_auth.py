import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from src.adapters.db.models import User, KYCLevel

@pytest.mark.asyncio
async def test_register_user(client: AsyncClient):
    response = await client.post(
        "/api/v1/register",
        json={
            "email": "test@example.com",
            "phone": "+2348000000000",
            "password": "strongpassword123"
        }
    )
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "test@example.com"
    assert data["phone"] == "+2348000000000"
    assert "id" in data
    assert data["kyc_level"] == KYCLevel.TIER_0.value

@pytest.mark.asyncio
async def test_register_user_duplicate_email(client: AsyncClient):
    # First registration
    await client.post(
        "/api/v1/register",
        json={
            "email": "duplicate@example.com",
            "phone": "+2348000000001",
            "password": "strongpassword123"
        }
    )
    # Second registration with same email
    response = await client.post(
        "/api/v1/register",
        json={
            "email": "duplicate@example.com",
            "phone": "+2348000000002",
            "password": "strongpassword123"
        }
    )
    assert response.status_code == 400
    assert "Email is already registered" in response.json()["detail"]

@pytest.mark.asyncio
async def test_login_user(client: AsyncClient):
    # Register
    await client.post(
        "/api/v1/register",
        json={
            "email": "login@example.com",
            "phone": "+2348000000003",
            "password": "strongpassword123"
        }
    )
    # Login
    response = await client.post(
        "/api/v1/login",
        json={
            "username": "login@example.com",
            "password": "strongpassword123"
        }
    )
    assert response.status_code == 200
    tokens = response.json()
    assert "access_token" in tokens
    assert "refresh_token" in tokens
    assert tokens["token_type"] == "bearer"

@pytest.mark.asyncio
async def test_login_user_invalid_credentials(client: AsyncClient):
    response = await client.post(
        "/api/v1/login",
        json={
            "username": "nonexistent@example.com",
            "password": "wrongpassword"
        }
    )
    assert response.status_code == 401
    assert "Invalid credentials" in response.json()["detail"]

@pytest.mark.asyncio
async def test_otp_flow(client: AsyncClient):
    # Request OTP
    resp_req = await client.post(
        "/api/v1/otp/request",
        json={
            "channel": "email",
            "target": "otp@example.com"
        }
    )
    assert resp_req.status_code == 200
    data = resp_req.json()
    assert "code" in data
    code = data["code"]

    # Verify OTP
    resp_ver = await client.post(
        "/api/v1/otp/verify",
        json={
            "target": "otp@example.com",
            "code": code
        }
    )
    assert resp_ver.status_code == 200
    assert resp_ver.json() == {"verified": True}

@pytest.mark.asyncio
async def test_kyc_verification_flow(client: AsyncClient):
    # Register
    reg_resp = await client.post(
        "/api/v1/register",
        json={
            "email": "kyc@example.com",
            "phone": "+2348000000004",
            "password": "strongpassword123"
        }
    )
    assert reg_resp.status_code == 201

    # Login to get token
    login_resp = await client.post(
        "/api/v1/login",
        json={
            "username": "kyc@example.com",
            "password": "strongpassword123"
        }
    )
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Verify BVN (Upgrades to Tier 1)
    kyc_resp = await client.post(
        "/api/v1/kyc/verify",
        json={
            "bvn": "12345678901"
        },
        headers=headers
    )
    assert kyc_resp.status_code == 200
    data = kyc_resp.json()
    assert data["kyc_level"] == KYCLevel.TIER_1.value

    # Verify NIN (Upgrades to Tier 2)
    kyc_resp = await client.post(
        "/api/v1/kyc/verify",
        json={
            "nin": "12345678901"
        },
        headers=headers
    )
    assert kyc_resp.status_code == 200
    data = kyc_resp.json()
    assert data["kyc_level"] == KYCLevel.TIER_2.value

    # Verify Face Image (Upgrades to Tier 3)
    kyc_resp = await client.post(
        "/api/v1/kyc/verify",
        json={
            "face_image_url": "https://example.com/face.jpg"
        },
        headers=headers
    )
    assert kyc_resp.status_code == 200
    data = kyc_resp.json()
    assert data["kyc_level"] == KYCLevel.TIER_3.value
    assert data["face_verified"] is True

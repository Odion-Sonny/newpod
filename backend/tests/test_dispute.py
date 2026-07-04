import pytest
import io
import uuid
import hashlib
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from src.adapters.db.models import EscrowStatus, DisputeStatus, User, Role
from src.adapters.db.repositories.user_repository import SQLAlchemyUserRepository

@pytest.mark.asyncio
async def test_dispute_lifecycle(client: AsyncClient, db: AsyncSession):
    # 1. Register and login Buyer & Seller
    seller_reg = await client.post(
        "/api/v1/register",
        json={"email": "seller_disp@example.com", "phone": "+2348000000010", "password": "password123"}
    )
    seller_id = seller_reg.json()["id"]

    seller_login = await client.post(
        "/api/v1/login",
        json={"username": "seller_disp@example.com", "password": "password123"}
    )
    seller_headers = {"Authorization": f"Bearer {seller_login.json()['access_token']}"}

    buyer_reg = await client.post(
        "/api/v1/register",
        json={"email": "buyer_disp@example.com", "phone": "+2348000000011", "password": "password123"}
    )
    buyer_id = buyer_reg.json()["id"]

    buyer_login = await client.post(
        "/api/v1/login",
        json={"username": "buyer_disp@example.com", "password": "password123"}
    )
    buyer_headers = {"Authorization": f"Bearer {buyer_login.json()['access_token']}"}

    # Fund Buyer's Wallet & Register addresses
    # Deposit funds via webhook
    ref = f"dep-ref-{uuid.uuid4().hex[:6]}"
    await client.post(
        "/api/v1/payments/webhook",
        json={
            "event": "charge.success",
            "data": {
                "reference": ref,
                "amount": 200000 * 100, # 200,000 NGN in kobo
                "status": "success",
                "customer": {"email": "buyer_disp@example.com"}
            }
        },
        headers={"x-paystack-signature": "mock-signature"}
    )

    # Seller creates a product
    product_resp = await client.post(
        "/api/v1/products",
        json={
            "title": "iPhone 15 Pro",
            "description": "Premium Apple Phone",
            "price": 180000.0,
            "stock": 3,
            "images": []
        },
        headers=seller_headers
    )
    product_id = product_resp.json()["id"]

    # Buyer creates delivery address
    address_resp = await client.post(
        "/api/v1/addresses",
        json={
            "street": "No 5 Allen Avenue",
            "city": "Ikeja",
            "state": "Lagos",
            "country": "Nigeria",
            "postal_code": "100001",
            "is_default": True
        },
        headers=buyer_headers
    )
    address_id = address_resp.json()["id"]

    # Buyer places an order
    order_resp = await client.post(
        "/api/v1/orders",
        json={
            "seller_id": seller_id,
            "items": [{"product_id": product_id, "quantity": 1}],
            "delivery_address_id": address_id
        },
        headers=buyer_headers
    )
    order_id = order_resp.json()["id"]

    esc_res = await client.get(f"/api/v1/escrows/order/{order_id}")
    escrow_id = esc_res.json()["id"]

    # Secure payment
    pay_res = await client.post(f"/api/v1/escrows/{escrow_id}/secure-payment", headers=buyer_headers)
    assert pay_res.status_code == 200

    # Seller accepts, packs, ships
    await client.post(f"/api/v1/escrows/{escrow_id}/accept", headers=seller_headers)
    await client.post(f"/api/v1/escrows/{escrow_id}/pack", headers=seller_headers)
    await client.post(f"/api/v1/escrows/{escrow_id}/ship?tracking_number=123&courier_provider=DHL", headers=seller_headers)

    # Verify Escrow is SHIPPED
    esc_check = await client.get(f"/api/v1/escrows/order/{order_id}")
    assert esc_check.json()["status"] == EscrowStatus.SHIPPED.value

    # Raise Dispute
    disp_res = await client.post(
        "/api/v1/disputes",
        json={"escrow_id": escrow_id, "reason": "The item received is fake or damaged during transit"},
        headers=buyer_headers
    )
    assert disp_res.status_code == 201
    dispute_id = disp_res.json()["id"]
    assert disp_res.json()["status"] == DisputeStatus.OPEN.value

    # Verify Escrow is DISPUTED
    esc_check = await client.get(f"/api/v1/escrows/order/{order_id}")
    assert esc_check.json()["status"] == EscrowStatus.DISPUTED.value

    # Try to dispute again (should raise 400 because escrow is no longer in SHIPPED/DELIVERED/INSPECTION_WINDOW)
    disp_fail = await client.post(
        "/api/v1/disputes",
        json={"escrow_id": escrow_id, "reason": "Another dispute reason"},
        headers=buyer_headers
    )
    assert disp_fail.status_code == 400

    # Try to upload evidence from random user (Unauthorized)
    random_reg = await client.post(
        "/api/v1/register",
        json={"email": "random@example.com", "phone": "+2348000000012", "password": "password123"}
    )
    random_login = await client.post(
        "/api/v1/login",
        json={"username": "random@example.com", "password": "password123"}
    )
    random_headers = {"Authorization": f"Bearer {random_login.json()['access_token']}"}

    evidence_fail = await client.post(
        f"/api/v1/disputes/{dispute_id}/evidence",
        data={"file_type": "PHOTO"},
        files={"file": ("test.png", io.BytesIO(b"dummy image data"), "image/png")},
        headers=random_headers
    )
    assert evidence_fail.status_code == 403

    # Upload evidence from buyer
    evidence_res = await client.post(
        f"/api/v1/disputes/{dispute_id}/evidence",
        data={"file_type": "PHOTO"},
        files={"file": ("test.png", io.BytesIO(b"dummy image data"), "image/png")},
        headers=buyer_headers
    )
    assert evidence_res.status_code == 201
    assert evidence_res.json()["hash"] == hashlib.sha256(b"dummy image data").hexdigest()

    # Upload evidence from seller
    evidence_seller_res = await client.post(
        f"/api/v1/disputes/{dispute_id}/evidence",
        data={"file_type": "DOCUMENT"},
        files={"file": ("receipt.pdf", io.BytesIO(b"dummy receipt data"), "application/pdf")},
        headers=seller_headers
    )
    assert evidence_seller_res.status_code == 201

    # Fetch Dispute details
    details_res = await client.get(f"/api/v1/disputes/{dispute_id}", headers=buyer_headers)
    assert details_res.status_code == 200
    assert len(details_res.json()["evidence"]) == 2
    assert len(details_res.json()["timeline_logs"]) == 3 # Opened + 2 evidence submissions

    # Register and assign ADMIN role
    admin_reg = await client.post(
        "/api/v1/register",
        json={"email": "admin@example.com", "phone": "+2348000000013", "password": "adminpassword123"}
    )
    admin_id = admin_reg.json()["id"]

    # Assign role to admin in database session
    user_repo = SQLAlchemyUserRepository(db)
    admin_user = await user_repo.get_by_id(admin_id)
    admin_role = await user_repo.get_role_by_name("ADMIN")
    if not admin_role:
        admin_role = await user_repo.create_role("ADMIN")
    admin_user.roles.append(admin_role)
    await user_repo.update(admin_user)
    await db.commit()

    admin_login = await client.post(
        "/api/v1/login",
        json={"username": "admin@example.com", "password": "adminpassword123"}
    )
    admin_headers = {"Authorization": f"Bearer {admin_login.json()['access_token']}"}

    # Resolve Dispute (verdict = REFUND_BUYER)
    res_details = "Refunding the buyer because the seller shipped the wrong product model."
    resolve_res = await client.post(
        f"/api/v1/disputes/{dispute_id}/resolve",
        json={"verdict": "REFUND_BUYER", "resolution_details": res_details},
        headers=admin_headers
    )
    assert resolve_res.status_code == 200
    assert resolve_res.json()["status"] == DisputeStatus.RESOLVED.value

    # Verify Escrow is REFUNDED
    esc_refunded = await client.get(f"/api/v1/escrows/order/{order_id}")
    assert esc_refunded.json()["status"] == EscrowStatus.REFUNDED.value

    # Verify Buyer got the refund in their wallet
    buyer_wallet = await client.get("/api/v1/wallet/me", headers=buyer_headers)
    # They deposited 200,000 NGN, ordered for 180,000 NGN (secured payment), were refunded 180,000 NGN.
    # Total wallet balance should be 200,000 NGN.
    assert buyer_wallet.json()["balance"] == 200000.0

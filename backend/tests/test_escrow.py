import pytest
from httpx import AsyncClient
from src.adapters.db.models import EscrowStatus

@pytest.mark.asyncio
async def test_escrow_happy_path(client: AsyncClient):
    # 1. Register and login Buyer & Seller
    seller_reg = await client.post(
        "/api/v1/register",
        json={"email": "seller@example.com", "phone": "+2348000000005", "password": "sellerpassword123"}
    )
    assert seller_reg.status_code == 201
    seller_id = seller_reg.json()["id"]

    seller_login = await client.post(
        "/api/v1/login",
        json={"username": "seller@example.com", "password": "sellerpassword123"}
    )
    seller_headers = {"Authorization": f"Bearer {seller_login.json()['access_token']}"}

    buyer_reg = await client.post(
        "/api/v1/register",
        json={"email": "buyer@example.com", "phone": "+2348000000006", "password": "buyerpassword123"}
    )
    buyer_id = buyer_reg.json()["id"]

    buyer_login = await client.post(
        "/api/v1/login",
        json={"username": "buyer@example.com", "password": "buyerpassword123"}
    )
    buyer_headers = {"Authorization": f"Bearer {buyer_login.json()['access_token']}"}

    # 2. Seller creates a product
    product_resp = await client.post(
        "/api/v1/products",
        json={
            "title": "MacBook Pro M3",
            "description": "High performance development machine with 32GB RAM",
            "price": 1500000.0,
            "stock": 5,
            "images": ["https://example.com/macbook.png"]
        },
        headers=seller_headers
    )
    product_id = product_resp.json()["id"]

    # 3. Buyer creates a delivery address
    address_resp = await client.post(
        "/api/v1/addresses",
        json={
            "street": "123 Alaba Market Road",
            "city": "Lagos",
            "state": "Lagos",
            "country": "Nigeria",
            "postal_code": "100001",
            "is_default": True
        },
        headers=buyer_headers
    )
    address_id = address_resp.json()["id"]

    # 4. Buyer places an order
    order_resp = await client.post(
        "/api/v1/orders",
        json={
            "seller_id": seller_id,
            "items": [{"product_id": product_id, "quantity": 1}],
            "delivery_address_id": address_id
        },
        headers=buyer_headers
    )
    assert order_resp.status_code == 201
    order_id = order_resp.json()["id"]

    # 5. Fetch the Escrow object
    escrow_resp = await client.get(f"/api/v1/escrows/order/{order_id}")
    assert escrow_resp.status_code == 200
    escrow_data = escrow_resp.json()
    escrow_id = escrow_data["id"]
    assert escrow_data["status"] == EscrowStatus.CREATED.value

    # 6. Secure payment
    pay_resp = await client.post(f"/api/v1/escrows/{escrow_id}/secure-payment")
    assert pay_resp.status_code == 200
    assert pay_resp.json()["status"] == EscrowStatus.PAYMENT_SECURED.value

    # 7. Seller accepts order
    accept_resp = await client.post(f"/api/v1/escrows/{escrow_id}/accept", headers=seller_headers)
    assert accept_resp.status_code == 200
    assert accept_resp.json()["status"] == EscrowStatus.SELLER_ACCEPTED.value

    # 8. Seller packs order
    pack_resp = await client.post(f"/api/v1/escrows/{escrow_id}/pack", headers=seller_headers)
    assert pack_resp.status_code == 200
    assert pack_resp.json()["status"] == EscrowStatus.PACKED.value

    # 9. Seller ships order
    ship_resp = await client.post(
        f"/api/v1/escrows/{escrow_id}/ship?tracking_number=TRK12345&courier_provider=DHL",
        headers=seller_headers
    )
    assert ship_resp.status_code == 200
    assert ship_resp.json()["status"] == EscrowStatus.SHIPPED.value

    # 10. Deliver order (courier updates)
    deliv_resp = await client.post(f"/api/v1/escrows/{escrow_id}/deliver")
    assert deliv_resp.status_code == 200
    # DELIVERED transitions directly to INSPECTION_WINDOW
    assert deliv_resp.json()["status"] == EscrowStatus.INSPECTION_WINDOW.value

    # 11. Buyer releases escrow
    rel_resp = await client.post(f"/api/v1/escrows/{escrow_id}/release", headers=buyer_headers)
    assert rel_resp.status_code == 200
    assert rel_resp.json()["status"] == EscrowStatus.RELEASED.value

@pytest.mark.asyncio
async def test_escrow_invalid_transition(client: AsyncClient):
    # Setup seller/buyer/product/address/order
    seller_reg = await client.post(
        "/api/v1/register",
        json={"email": "s2@example.com", "phone": "+2348000000007", "password": "sellerpassword123"}
    )
    seller_id = seller_reg.json()["id"]

    seller_login = await client.post(
        "/api/v1/login",
        json={"username": "s2@example.com", "password": "sellerpassword123"}
    )
    seller_headers = {"Authorization": f"Bearer {seller_login.json()['access_token']}"}

    buyer_reg = await client.post(
        "/api/v1/register",
        json={"email": "b2@example.com", "phone": "+2348000000008", "password": "buyerpassword123"}
    )
    buyer_login = await client.post(
        "/api/v1/login",
        json={"username": "b2@example.com", "password": "buyerpassword123"}
    )
    buyer_headers = {"Authorization": f"Bearer {buyer_login.json()['access_token']}"}

    product_resp = await client.post(
        "/api/v1/products",
        json={"title": "iPhone 15", "description": "Apple iPhone 15 128GB", "price": 1000000.0, "stock": 2, "images": []},
        headers=seller_headers
    )
    product_id = product_resp.json()["id"]

    address_resp = await client.post(
        "/api/v1/addresses",
        json={"street": "Str", "city": "City", "state": "State", "country": "Nig", "is_default": True},
        headers=buyer_headers
    )
    address_id = address_resp.json()["id"]

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

    escrow_resp = await client.get(f"/api/v1/escrows/order/{order_id}")
    escrow_id = escrow_resp.json()["id"]

    # Try to ship directly (unpaid) -> Should fail
    ship_resp = await client.post(
        f"/api/v1/escrows/{escrow_id}/ship?tracking_number=TRK12345&courier_provider=DHL",
        headers=seller_headers
    )
    assert ship_resp.status_code == 400
    assert "Cannot ship order in status" in ship_resp.json()["detail"]

@pytest.mark.asyncio
async def test_escrow_cancellation(client: AsyncClient):
    seller_reg = await client.post(
        "/api/v1/register",
        json={"email": "s3@example.com", "phone": "+2348000000009", "password": "sellerpassword123"}
    )
    seller_id = seller_reg.json()["id"]

    seller_login = await client.post(
        "/api/v1/login",
        json={"username": "s3@example.com", "password": "sellerpassword123"}
    )
    seller_headers = {"Authorization": f"Bearer {seller_login.json()['access_token']}"}

    buyer_reg = await client.post(
        "/api/v1/register",
        json={"email": "b3@example.com", "phone": "+2348000000010", "password": "buyerpassword123"}
    )
    buyer_login = await client.post(
        "/api/v1/login",
        json={"username": "b3@example.com", "password": "buyerpassword123"}
    )
    buyer_headers = {"Authorization": f"Bearer {buyer_login.json()['access_token']}"}

    product_resp = await client.post(
        "/api/v1/products",
        json={"title": "iPhone 15", "description": "Apple iPhone 15 128GB", "price": 1000000.0, "stock": 2, "images": []},
        headers=seller_headers
    )
    product_id = product_resp.json()["id"]

    address_resp = await client.post(
        "/api/v1/addresses",
        json={"street": "Str", "city": "City", "state": "State", "country": "Nig", "is_default": True},
        headers=buyer_headers
    )
    address_id = address_resp.json()["id"]

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

    escrow_resp = await client.get(f"/api/v1/escrows/order/{order_id}")
    escrow_id = escrow_resp.json()["id"]

    # 1. Cancel unpaid escrow (Buyer cancels)
    cancel_resp = await client.post(f"/api/v1/escrows/{escrow_id}/cancel", headers=buyer_headers)
    assert cancel_resp.status_code == 200
    assert cancel_resp.json()["status"] == EscrowStatus.CANCELLED.value

    # Verify stock restored
    prod_check = await client.get("/api/v1/products?limit=100")
    products = prod_check.json()
    target_product = next(p for p in products if p["id"] == product_id)
    assert target_product["stock"] == 2 # Restored back to 2 from 1

@pytest.mark.asyncio
async def test_escrow_auto_release_task(client: AsyncClient, db: AsyncSession):
    # Setup seller/buyer/product/address/order
    seller_reg = await client.post(
        "/api/v1/register",
        json={"email": "s4@example.com", "phone": "+2348000000011", "password": "sellerpassword123"}
    )
    seller_id = seller_reg.json()["id"]

    seller_login = await client.post(
        "/api/v1/login",
        json={"username": "s4@example.com", "password": "sellerpassword123"}
    )
    seller_headers = {"Authorization": f"Bearer {seller_login.json()['access_token']}"}

    buyer_reg = await client.post(
        "/api/v1/register",
        json={"email": "b4@example.com", "phone": "+2348000000012", "password": "buyerpassword123"}
    )
    buyer_login = await client.post(
        "/api/v1/login",
        json={"username": "b4@example.com", "password": "buyerpassword123"}
    )
    buyer_headers = {"Authorization": f"Bearer {buyer_login.json()['access_token']}"}

    product_resp = await client.post(
        "/api/v1/products",
        json={"title": "iPhone 15", "description": "Apple iPhone 15 128GB", "price": 1000000.0, "stock": 2, "images": []},
        headers=seller_headers
    )
    product_id = product_resp.json()["id"]

    address_resp = await client.post(
        "/api/v1/addresses",
        json={"street": "Str", "city": "City", "state": "State", "country": "Nig", "is_default": True},
        headers=buyer_headers
    )
    address_id = address_resp.json()["id"]

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

    escrow_resp = await client.get(f"/api/v1/escrows/order/{order_id}")
    escrow_id = escrow_resp.json()["id"]

    # Secure payment
    await client.post(f"/api/v1/escrows/{escrow_id}/secure-payment")
    # Seller accepts
    await client.post(f"/api/v1/escrows/{escrow_id}/accept", headers=seller_headers)
    # Seller packs
    await client.post(f"/api/v1/escrows/{escrow_id}/pack", headers=seller_headers)
    # Seller ships
    await client.post(
        f"/api/v1/escrows/{escrow_id}/ship?tracking_number=TRK12345&courier_provider=DHL",
        headers=seller_headers
    )
    # Deliver -> Transitions to INSPECTION_WINDOW
    await client.post(f"/api/v1/escrows/{escrow_id}/deliver")

    # Manually backdate the updated_at timestamp in the database to > 24 hours ago
    from sqlalchemy import update
    from datetime import datetime, timezone, timedelta
    from src.adapters.db.models import Escrow
    import uuid

    past_time = datetime.now(timezone.utc) - timedelta(hours=25)
    await db.execute(
        update(Escrow)
        .where(Escrow.id == uuid.UUID(escrow_id))
        .values(updated_at=past_time)
    )
    await db.commit()

    # Now execute the Celery task function directly/synchronously
    from src.use_cases.tasks import auto_release_expired_escrows_async
    await auto_release_expired_escrows_async(hours=24, db=db)

    # Fetch the escrow again and verify it is RELEASED
    # (Since the test runs within a transaction using NullPool, we can get a new session to query)
    escrow_check = await client.get(f"/api/v1/escrows/{escrow_id}")
    assert escrow_check.status_code == 200
    assert escrow_check.json()["status"] == EscrowStatus.RELEASED.value


import uuid
from fastapi.testclient import TestClient
from src.main import app
from src.core.database import get_db
from tests.conftest import TestAsyncSessionLocal

def test_chat_websocket_and_rest():
    # Override get_db to yield a fresh session on the TestClient's loop
    async def override_get_db():
        async with TestAsyncSessionLocal() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()

    app.dependency_overrides[get_db] = override_get_db

    # Generate unique emails and phone numbers to avoid conflicts
    unique_suffix = uuid.uuid4().hex[:6]
    seller_email = f"seller_chat_{unique_suffix}@example.com"
    seller_phone = f"+2348000000{unique_suffix[:4]}"
    buyer_email = f"buyer_chat_{unique_suffix}@example.com"
    buyer_phone = f"+2348000001{unique_suffix[:4]}"

    # Use TestClient for websocket testing (as httpx doesn't support websockets)
    with TestClient(app) as client:
        # Register and login Buyer & Seller
        seller_reg = client.post(
            "/api/v1/register",
            json={"email": seller_email, "phone": seller_phone, "password": "password123"}
        )
        assert seller_reg.status_code == 201
        seller_id = seller_reg.json()["id"]

        seller_login = client.post(
            "/api/v1/login",
            json={"username": seller_email, "password": "password123"}
        )
        seller_token = seller_login.json()["access_token"]
        seller_headers = {"Authorization": f"Bearer {seller_token}"}

        buyer_reg = client.post(
            "/api/v1/register",
            json={"email": buyer_email, "phone": buyer_phone, "password": "password123"}
        )
        assert buyer_reg.status_code == 201
        buyer_id = buyer_reg.json()["id"]

        buyer_login = client.post(
            "/api/v1/login",
            json={"username": buyer_email, "password": "password123"}
        )
        buyer_token = buyer_login.json()["access_token"]
        buyer_headers = {"Authorization": f"Bearer {buyer_token}"}

        # Fund Buyer's Wallet
        ref = f"dep-ref-{uuid.uuid4().hex[:6]}"
        client.post(
            "/api/v1/payments/webhook",
            json={
                "event": "charge.success",
                "data": {
                    "reference": ref,
                    "amount": 200000 * 100,
                    "status": "success",
                    "customer": {"email": buyer_email}
                }
            },
            headers={"x-paystack-signature": "mock-signature"}
        )

        # Seller creates a product
        product_resp = client.post(
            "/api/v1/products",
            json={
                "title": "MacBook Air M2",
                "description": "Premium laptop",
                "price": 100000.0,
                "stock": 2,
                "images": []
            },
            headers=seller_headers
        )
        product_id = product_resp.json()["id"]

        # Buyer creates delivery address
        address_resp = client.post(
            "/api/v1/addresses",
            json={
                "street": "No 1 Lekki Way",
                "city": "Lekki",
                "state": "Lagos",
                "country": "Nigeria",
                "postal_code": "105101",
                "is_default": True
            },
            headers=buyer_headers
        )
        address_id = address_resp.json()["id"]

        # Buyer places an order
        order_resp = client.post(
            "/api/v1/orders",
            json={
                "seller_id": seller_id,
                "items": [{"product_id": product_id, "quantity": 1}],
                "delivery_address_id": address_id
            },
            headers=buyer_headers
        )
        order_id = order_resp.json()["id"]

        esc_res = client.get(f"/api/v1/escrows/order/{order_id}")
        escrow_id = esc_res.json()["id"]

        # Secure payment
        pay_res = client.post(f"/api/v1/escrows/{escrow_id}/secure-payment", headers=buyer_headers)
        assert pay_res.status_code == 200

        # --- WebSocket Test: Buyer connects and sends message ---
        with client.websocket_connect(f"/api/v1/escrows/{escrow_id}/chat/ws?token={buyer_token}") as buyer_ws:
            # On join, read receipt is broadcasted
            buyer_join_event = buyer_ws.receive_json()
            assert buyer_join_event["type"] == "read_receipt"
            assert buyer_join_event["reader_id"] == buyer_id

            # Buyer sends a message
            buyer_ws.send_json({
                "type": "message",
                "content": "Hello Seller, is it ready for pick up?"
            })

            # Buyer receives their own broadcasted message
            buyer_msg_event = buyer_ws.receive_json()
            assert buyer_msg_event["type"] == "message"
            assert buyer_msg_event["content"] == "Hello Seller, is it ready for pick up?"

        # --- WebSocket Test: Seller connects and sends message ---
        with client.websocket_connect(f"/api/v1/escrows/{escrow_id}/chat/ws?token={seller_token}") as seller_ws:
            # On join, read receipt is broadcasted
            seller_join_event = seller_ws.receive_json()
            assert seller_join_event["type"] == "read_receipt"
            assert seller_join_event["reader_id"] == seller_id

            # Seller sends a message
            seller_ws.send_json({
                "type": "message",
                "content": "Yes, I will package and ship today."
            })

            # Seller receives their own broadcasted message
            seller_msg_event = seller_ws.receive_json()
            assert seller_msg_event["type"] == "message"
            assert seller_msg_event["content"] == "Yes, I will package and ship today."

        # --- REST API Test: Fetch conversation history ---
        rest_res = client.get(f"/api/v1/escrows/{escrow_id}/chat/messages", headers=buyer_headers)
        assert rest_res.status_code == 200
        messages = rest_res.json()
        assert len(messages) == 2
        assert messages[0]["content"] == "Hello Seller, is it ready for pick up?"
        assert messages[1]["content"] == "Yes, I will package and ship today."

        # Unauthorized user gets 403 Forbidden
        unauth_reg = client.post(
            "/api/v1/register",
            json={"email": f"unauth_chat_{unique_suffix}@example.com", "phone": f"+2348000002{unique_suffix[:4]}", "password": "password123"}
        )
        unauth_login = client.post(
            "/api/v1/login",
            json={"username": f"unauth_chat_{unique_suffix}@example.com", "password": "password123"}
        )
        unauth_headers = {"Authorization": f"Bearer {unauth_login.json()['access_token']}"}

        rest_fail = client.get(f"/api/v1/escrows/{escrow_id}/chat/messages", headers=unauth_headers)
        assert rest_fail.status_code == 403

    app.dependency_overrides.clear()

import pytest
from httpx import AsyncClient
from src.adapters.db.models import EscrowStatus

@pytest.mark.asyncio
async def test_ledger_deposit_and_withdrawal(client: AsyncClient):
    # 1. Register and login User
    user_reg = await client.post(
        "/api/v1/register",
        json={"email": "walletuser@example.com", "phone": "+2348000000200", "password": "walletpassword123"}
    )
    assert user_reg.status_code == 201

    login_resp = await client.post(
        "/api/v1/login",
        json={"username": "walletuser@example.com", "password": "walletpassword123"}
    )
    headers = {"Authorization": f"Bearer {login_resp.json()['access_token']}"}

    # 2. Get wallet balance (initial should be 0.0)
    wallet_resp = await client.get("/api/v1/wallet/me", headers=headers)
    assert wallet_resp.status_code == 200
    assert wallet_resp.json()["balance"] == 0.0

    # 3. Initiate Deposit
    deposit_resp = await client.post(
        "/api/v1/wallet/deposit",
        json={"amount": 50000.0},
        headers=headers
    )
    assert deposit_resp.status_code == 200
    deposit_data = deposit_resp.json()
    reference = deposit_data["reference"]
    assert deposit_data["authorization_url"].startswith("https://checkout.paystack.com/mock-dep-")

    # 4. Simulate Paystack Success Webhook
    webhook_payload = {
        "event": "charge.success",
        "data": {
            "reference": reference,
            "amount": 5000000, # 50000 NGN in kobo
            "status": "success",
            "customer": {
                "email": "walletuser@example.com"
            }
        }
    }
    # Send webhook
    webhook_resp = await client.post(
        "/api/v1/payments/webhook",
        json=webhook_payload,
        headers={"x-paystack-signature": "mock-signature"}
    )
    assert webhook_resp.status_code == 200

    # 5. Check wallet balance updated
    wallet_resp = await client.get("/api/v1/wallet/me", headers=headers)
    assert wallet_resp.json()["balance"] == 50000.0

    # 6. Check ledger history
    ledger_resp = await client.get("/api/v1/wallet/ledger", headers=headers)
    assert ledger_resp.status_code == 200
    entries = ledger_resp.json()
    assert len(entries) == 1
    assert entries[0]["entry_type"] == "CREDIT"
    assert entries[0]["amount"] == 50000.0

    # 7. Perform Withdrawal
    withdraw_resp = await client.post(
        "/api/v1/wallet/withdraw",
        json={
            "amount": 20000.0,
            "bank_code": "058",
            "account_number": "0123456789",
            "recipient_name": "Wallet User"
        },
        headers=headers
    )
    assert withdraw_resp.status_code == 200

    # 8. Check balance and ledger after withdrawal
    wallet_resp = await client.get("/api/v1/wallet/me", headers=headers)
    assert wallet_resp.json()["balance"] == 30000.0

    ledger_resp = await client.get("/api/v1/wallet/ledger", headers=headers)
    entries = ledger_resp.json()
    assert len(entries) == 2
    assert entries[0]["entry_type"] == "DEBIT"
    assert entries[0]["amount"] == 20000.0

    # 9. Try to withdraw more than balance -> Should fail
    fail_withdraw = await client.post(
        "/api/v1/wallet/withdraw",
        json={
            "amount": 40000.0,
            "bank_code": "058",
            "account_number": "0123456789",
            "recipient_name": "Wallet User"
        },
        headers=headers
    )
    assert fail_withdraw.status_code == 400
    assert "Insufficient funds in wallet" in fail_withdraw.json()["detail"]


@pytest.mark.asyncio
async def test_escrow_payout_and_refund_ledger_integration(client: AsyncClient):
    # Setup Buyer & Seller
    seller_reg = await client.post(
        "/api/v1/register",
        json={"email": "s_ledger@example.com", "phone": "+2348000000300", "password": "password"}
    )
    seller_id = seller_reg.json()["id"]
    seller_login = await client.post("/api/v1/login", json={"username": "s_ledger@example.com", "password": "password"})
    seller_headers = {"Authorization": f"Bearer {seller_login.json()['access_token']}"}

    buyer_reg = await client.post(
        "/api/v1/register",
        json={"email": "b_ledger@example.com", "phone": "+2348000000400", "password": "password"}
    )
    buyer_login = await client.post("/api/v1/login", json={"username": "b_ledger@example.com", "password": "password"})
    buyer_headers = {"Authorization": f"Bearer {buyer_login.json()['access_token']}"}

    # Fund Buyer's Wallet first (100k NGN)
    dep_res = await client.post("/api/v1/wallet/deposit", json={"amount": 100000.0}, headers=buyer_headers)
    ref = dep_res.json()["reference"]
    await client.post(
        "/api/v1/payments/webhook",
        json={
            "event": "charge.success",
            "data": {
                "reference": ref,
                "amount": 10000000,
                "status": "success",
                "customer": {"email": "b_ledger@example.com"}
            }
        }
    )

    # Verify buyer balance
    buyer_wallet = await client.get("/api/v1/wallet/me", headers=buyer_headers)
    assert buyer_wallet.json()["balance"] == 100000.0

    # Seller creates a product (100k NGN)
    prod_res = await client.post(
        "/api/v1/products",
        json={"title": "Test Item", "description": "Short Description", "price": 100000.0, "stock": 1},
        headers=seller_headers
    )
    product_id = prod_res.json()["id"]

    # Buyer creates address
    addr_res = await client.post(
        "/api/v1/addresses",
        json={"street": "1 St", "city": "City", "state": "State", "country": "Nigeria", "is_default": True},
        headers=buyer_headers
    )
    addr_id = addr_res.json()["id"]

    # Buyer places order
    order_res = await client.post(
        "/api/v1/orders",
        json={"seller_id": seller_id, "items": [{"product_id": product_id, "quantity": 1}], "delivery_address_id": addr_id},
        headers=buyer_headers
    )
    order_id = order_res.json()["id"]

    # Fetch Escrow
    esc_res = await client.get(f"/api/v1/escrows/order/{order_id}")
    escrow_id = esc_res.json()["id"]
    # Platform fee is 1.5% of 100,000 = 1500 NGN
    assert esc_res.json()["fee"] == 1500.0

    # Buyer secures payment using wallet balance (internal secure payment)
    # We call secure-payment endpoint which internally calls ledger.secure_escrow_payment
    pay_res = await client.post(f"/api/v1/escrows/{escrow_id}/secure-payment", headers=buyer_headers)
    assert pay_res.status_code == 200

    # Assert Buyer's wallet balance is now 0.0 (funds debited/locked)
    buyer_wallet = await client.get("/api/v1/wallet/me", headers=buyer_headers)
    assert buyer_wallet.json()["balance"] == 0.0

    # Advance Escrow state to release point: Accept -> Pack -> Ship -> Deliver
    await client.post(f"/api/v1/escrows/{escrow_id}/accept", headers=seller_headers)
    await client.post(f"/api/v1/escrows/{escrow_id}/pack", headers=seller_headers)
    await client.post(f"/api/v1/escrows/{escrow_id}/ship?tracking_number=123&courier_provider=DHL", headers=seller_headers)
    await client.post(f"/api/v1/escrows/{escrow_id}/deliver")

    # Release Escrow
    rel_res = await client.post(f"/api/v1/escrows/{escrow_id}/release", headers=buyer_headers)
    assert rel_res.status_code == 200
    assert rel_res.json()["status"] == EscrowStatus.RELEASED.value

    # Verify Seller's wallet has been credited with payout amount (100,000 - 1500 = 98,500 NGN)
    seller_wallet = await client.get("/api/v1/wallet/me", headers=seller_headers)
    assert seller_wallet.json()["balance"] == 98500.0

    # 10. Check refund flow
    # Create another order (buyer must be funded first)
    # Fund Buyer's Wallet with 100k NGN again
    dep_res = await client.post("/api/v1/wallet/deposit", json={"amount": 100000.0}, headers=buyer_headers)
    ref = dep_res.json()["reference"]
    await client.post(
        "/api/v1/payments/webhook",
        json={
            "event": "charge.success",
            "data": {
                "reference": ref,
                "amount": 10000000,
                "status": "success",
                "customer": {"email": "b_ledger@example.com"}
            }
        }
    )

    # Restock product (seller increments stock)
    # Wait, we don't have update stock API, so let's just make a new product
    prod_res = await client.post(
        "/api/v1/products",
        json={"title": "Test Item 2", "description": "Short Description", "price": 100000.0, "stock": 1},
        headers=seller_headers
    )
    product_id_2 = prod_res.json()["id"]

    order_res_2 = await client.post(
        "/api/v1/orders",
        json={"seller_id": seller_id, "items": [{"product_id": product_id_2, "quantity": 1}], "delivery_address_id": addr_id},
        headers=buyer_headers
    )
    order_id_2 = order_res_2.json()["id"]

    esc_res_2 = await client.get(f"/api/v1/escrows/order/{order_id_2}")
    escrow_id_2 = esc_res_2.json()["id"]

    # Secure payment
    await client.post(f"/api/v1/escrows/{escrow_id_2}/secure-payment", headers=buyer_headers)
    buyer_wallet = await client.get("/api/v1/wallet/me", headers=buyer_headers)
    assert buyer_wallet.json()["balance"] == 0.0

    # Cancel Escrow (Buyer cancels created escrow or seller cancels paid escrow before shipping)
    # Here seller cancels paid escrow before shipping
    await client.post(f"/api/v1/escrows/{escrow_id_2}/accept", headers=seller_headers)
    cancel_res = await client.post(f"/api/v1/escrows/{escrow_id_2}/cancel", headers=seller_headers)
    assert cancel_res.status_code == 200

    # Assert Buyer's wallet is fully refunded (100k NGN)
    buyer_wallet = await client.get("/api/v1/wallet/me", headers=buyer_headers)
    assert buyer_wallet.json()["balance"] == 100000.0

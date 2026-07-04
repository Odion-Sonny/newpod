import httpx
import uuid
import hmac
import hashlib
from typing import Dict, Any, Optional
from src.core.config import settings

class PaystackClient:
    def __init__(self):
        self.secret_key = settings.SECRET_KEY  # Or settings.PAYSTACK_SECRET_KEY if available
        self.base_url = "https://api.paystack.co"
        self.headers = {
            "Authorization": f"Bearer {self.secret_key}",
            "Content-Type": "application/json",
        }

    async def initialize_transaction(
        self, email: str, amount_ngn: float, callback_url: str, reference: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Initialize payment request.
        Amount must be in kobo (NGN * 100).
        """
        ref = reference or f"paystack-init-{uuid.uuid4().hex[:12]}"
        amount_kobo = int(amount_ngn * 100)

        # Mock implementation for local/dev testing
        if not settings.DEBUG or not self.secret_key.startswith("sk_"):
            # Return Mock response
            return {
                "status": True,
                "message": "Authorization URL created (Mock)",
                "data": {
                    "authorization_url": f"https://checkout.paystack.com/mock-{ref}",
                    "access_code": f"access-{uuid.uuid4().hex[:8]}",
                    "reference": ref
                }
            }

        # Real Paystack API integration
        async with httpx.AsyncClient() as client:
            payload = {
                "email": email,
                "amount": amount_kobo,
                "callback_url": callback_url,
                "reference": ref
            }
            resp = await client.post(f"{self.base_url}/transaction/initialize", json=payload, headers=self.headers)
            resp.raise_for_status()
            return resp.json()

    async def verify_transaction(self, reference: str) -> Dict[str, Any]:
        """
        Verify transaction status by reference.
        """
        if not settings.DEBUG or not self.secret_key.startswith("sk_"):
            # Mock success verification
            return {
                "status": True,
                "message": "Verification successful (Mock)",
                "data": {
                    "id": 1234567,
                    "domain": "test",
                    "status": "success",
                    "reference": reference,
                    "amount": 100000, # 1000 NGN in kobo
                    "gateway_response": "Successful",
                    "paid_at": "2026-07-04T12:00:00Z",
                    "channel": "card",
                    "currency": "NGN",
                    "customer": {
                        "email": "user@example.com"
                    }
                }
            }

        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{self.base_url}/transaction/verify/{reference}", headers=self.headers)
            resp.raise_for_status()
            return resp.json()

    async def initiate_transfer(
        self, amount_ngn: float, recipient_code: str, reason: str, reference: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Initiate transfer / payout to seller bank account.
        """
        ref = reference or f"paystack-trf-{uuid.uuid4().hex[:12]}"
        amount_kobo = int(amount_ngn * 100)

        if not settings.DEBUG or not self.secret_key.startswith("sk_"):
            return {
                "status": True,
                "message": "Transfer initiated (Mock)",
                "data": {
                    "reference": ref,
                    "amount": amount_kobo,
                    "status": "success",
                    "transfer_code": f"TRF_{uuid.uuid4().hex[:12]}",
                    "recipient": recipient_code
                }
            }

        async with httpx.AsyncClient() as client:
            payload = {
                "source": "balance",
                "amount": amount_kobo,
                "recipient": recipient_code,
                "reason": reason,
                "reference": ref
            }
            resp = await client.post(f"{self.base_url}/transfer", json=payload, headers=self.headers)
            resp.raise_for_status()
            return resp.json()

    def verify_webhook_signature(self, payload: bytes, signature: str) -> bool:
        """
        Verify Paystack signature from request headers.
        """
        if not settings.DEBUG or not self.secret_key.startswith("sk_"):
            return True # In development, bypass signature check

        computed = hmac.new(
            self.secret_key.encode("utf-8"),
            payload,
            hashlib.sha512
        ).hexdigest()
        return hmac.compare_digest(computed, signature)

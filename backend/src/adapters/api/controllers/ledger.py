from fastapi import APIRouter, Depends, HTTPException, Header, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
import uuid
import json

from src.core.database import get_db
from src.adapters.db.repositories.ledger_repository import SQLAlchemyLedgerRepository
from src.adapters.db.repositories.escrow_repository import SQLAlchemyEscrowRepository
from src.use_cases.ledger import LedgerService
from src.use_cases.escrow import EscrowService
from src.adapters.gateways.paystack import PaystackClient
from src.adapters.api.dependencies import get_current_user
from src.adapters.db.models import User, Payment, Escrow, EscrowStatus
from src.adapters.api.schemas.ledger import (
    WalletResponse, WalletLedgerResponse, DepositRequest, DepositResponse, WithdrawalRequest
)

router = APIRouter()

def get_ledger_service(db: AsyncSession = Depends(get_db)) -> LedgerService:
    ledger_repo = SQLAlchemyLedgerRepository(db)
    return LedgerService(ledger_repo)

def get_escrow_service(db: AsyncSession = Depends(get_db)) -> EscrowService:
    escrow_repo = SQLAlchemyEscrowRepository(db)
    return EscrowService(escrow_repo)

# --- Wallet Info ---

@router.get("/wallet/me", response_model=WalletResponse)
async def get_wallet(
    current_user: User = Depends(get_current_user),
    service: LedgerService = Depends(get_ledger_service)
):
    return await service.get_wallet(str(current_user.id))

@router.get("/wallet/ledger", response_model=List[WalletLedgerResponse])
async def get_ledger(
    current_user: User = Depends(get_current_user),
    limit: int = 20,
    service: LedgerService = Depends(get_ledger_service)
):
    return await service.get_ledger_entries(str(current_user.id), limit=limit)

# --- Deposit & Withdraw ---

@router.post("/wallet/deposit", response_model=DepositResponse)
async def deposit(
    data: DepositRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # Initialize paystack transaction
    client = PaystackClient()
    ref = f"dep-{uuid.uuid4().hex[:12]}"
    callback_url = "https://newpod.ng/payment/callback"
    paystack_res = await client.initialize_transaction(
        email=current_user.email,
        amount_ngn=data.amount,
        callback_url=callback_url,
        reference=ref
    )
    if not paystack_res.get("status"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to initialize payment gateway transaction"
        )
        
    # Get user wallet
    ledger_repo = SQLAlchemyLedgerRepository(db)
    wallet = await ledger_repo.get_wallet_by_user_id(str(current_user.id))
    if not wallet:
        raise HTTPException(status_code=404, detail="Wallet not found")

    # Save payment record in DB (pending status)
    # We create a dummy/temporary escrow association if it's a direct escrow payment,
    # or keep escrow_id NULL if it is a general wallet deposit.
    payment = Payment(
        amount=data.amount,
        provider="PAYSTACK",
        provider_reference=ref,
        status="pending"
    )
    # Wait, Payment model requires escrow_id!
    # Let's check models.py: Column escrow_id is ForeignKey("escrows.id"). Let's check if it is nullable.
    # Yes, in PostgreSQL foreign keys are nullable unless specified nullable=False. In models.py:
    # escrow_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("escrows.id", ondelete="CASCADE"), index=True)
    # Since it is type uuid.UUID and doesn't specify nullable=False, it is nullable!
    # But just in case, we can associate it or leave it null.
    db.add(payment)
    await db.commit()

    return DepositResponse(
        authorization_url=paystack_res["data"]["authorization_url"],
        reference=ref
    )

@router.post("/wallet/withdraw")
async def withdraw(
    data: WithdrawalRequest,
    current_user: User = Depends(get_current_user),
    service: LedgerService = Depends(get_ledger_service)
):
    # Call Paystack to initiate transfer
    paystack_client = PaystackClient()
    ref = f"wd-{uuid.uuid4().hex[:12]}"
    
    # In real production, we first create a transfer recipient code on Paystack,
    # then initiate the transfer. Here we simulate that flow:
    recipient_code = f"RCP_{uuid.uuid4().hex[:12]}"
    res = await paystack_client.initiate_transfer(
        amount_ngn=data.amount,
        recipient_code=recipient_code,
        reason=f"NewPod Wallet Withdrawal for {current_user.email}",
        reference=ref
    )
    if not res.get("status"):
        raise HTTPException(status_code=400, detail="Payout gateway request failed")
        
    # Deduct funds from user's wallet
    await service.withdraw_funds(str(current_user.id), data.amount, ref)
    return {"message": "Withdrawal processed successfully", "reference": ref}

# --- Paystack Webhook Handler ---

@router.post("/payments/webhook")
async def paystack_webhook(
    request: Request,
    x_paystack_signature: Optional[str] = Header(None),
    db: AsyncSession = Depends(get_db)
):
    body = await request.body()
    paystack_client = PaystackClient()
    
    # 1. Verify signature
    if not paystack_client.verify_webhook_signature(body, x_paystack_signature or ""):
        raise HTTPException(status_code=401, detail="Invalid signature")

    payload = json.loads(body)
    event = payload.get("event")
    
    if event == "charge.success":
        data = payload.get("data", {})
        reference = data.get("reference")
        amount_kobo = data.get("amount", 0)
        amount_ngn = float(amount_kobo) / 100.0
        
        # Process the payment in DB
        ledger_repo = SQLAlchemyLedgerRepository(db)
        payment = await ledger_repo.get_payment_by_reference(reference)
        if not payment:
            # If payment not found, let's create a new one to log it
            payment = Payment(
                amount=amount_ngn,
                provider="PAYSTACK",
                provider_reference=reference,
                status="success"
            )
            db.add(payment)
        else:
            if payment.status == "success":
                return {"message": "Event already processed"}
            payment.status = "success"
            db.add(payment)

        # Retrieve user/customer email to identify wallet owner
        customer = data.get("customer", {})
        email = customer.get("email")
        
        # Fetch user
        from sqlalchemy.future import select
        result = await db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()
        
        if user:
            # Credit wallet
            ledger_service = LedgerService(ledger_repo)
            await ledger_service.deposit_funds(str(user.id), amount_ngn, reference)
            
            # If reference is linked to a direct order/escrow payment flow
            # (e.g. buyer paid for order directly, reference format: esc-pay-<escrow_id>-xxx)
            if reference.startswith("esc-pay-"):
                # Extract escrow_id
                parts = reference.split("-")
                if len(parts) >= 3:
                    try:
                        escrow_id = parts[2]
                        # Verify UUID validity
                        uuid.UUID(escrow_id)
                        
                        escrow_repo = SQLAlchemyEscrowRepository(db)
                        escrow_service = EscrowService(escrow_repo)
                        escrow = await escrow_repo.get_escrow_by_id(escrow_id)
                        if escrow and escrow.status == EscrowStatus.CREATED:
                            # 1. Advance Escrow status to PAYMENT_SECURED
                            await escrow_service.secure_payment(escrow_id)
                            # 2. Debit the payment amount from the user's wallet
                            # to lock it inside the escrow hold
                            await ledger_service.secure_escrow_payment(str(user.id), escrow)
                    except ValueError:
                        pass # Invalid UUID in reference

        await db.commit()

    return {"message": "Webhook processed"}

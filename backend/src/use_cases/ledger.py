import uuid
from decimal import Decimal
from fastapi import HTTPException, status
from src.domain.repositories.ledger_repository import LedgerRepositoryInterface
from src.adapters.db.models import (
    Wallet, WalletLedger, Transaction, LedgerEntryType,
    TransactionType, TransactionStatus, Escrow
)

class LedgerService:
    def __init__(self, ledger_repo: LedgerRepositoryInterface):
        self.ledger_repo = ledger_repo

    async def get_wallet(self, user_id: str) -> Wallet:
        wallet = await self.ledger_repo.get_wallet_by_user_id(user_id)
        if not wallet:
            raise HTTPException(status_code=404, detail="Wallet not found")
        return wallet

    async def get_ledger_entries(self, user_id: str, limit: int = 20) -> list:
        wallet = await self.get_wallet(user_id)
        return await self.ledger_repo.get_ledger_entries(str(wallet.id), limit=limit)

    async def deposit_funds(self, user_id: str, amount: float, reference: str) -> Transaction:
        # 1. Lock user's wallet
        wallet = await self.ledger_repo.get_wallet_by_user_id(user_id, lock=True)
        if not wallet:
            raise HTTPException(status_code=404, detail="Wallet not found")

        amt_decimal = Decimal(str(amount))
        balance_before = Decimal(str(wallet.balance))
        balance_after = balance_before + amt_decimal

        # 2. Update wallet balance
        wallet.balance = float(balance_after)
        await self.ledger_repo.update_wallet(wallet)

        # 3. Create Transaction
        tx = Transaction(
            reference=reference,
            transaction_type=TransactionType.DEPOSIT,
            status=TransactionStatus.SUCCESS,
            amount=amount,
            fee=0.0,
            receiver_wallet_id=wallet.id,
            description=f"Deposit of NGN {amount}"
        )
        created_tx = await self.ledger_repo.create_transaction(tx)

        # 4. Create Ledger Entry
        entry = WalletLedger(
            wallet_id=wallet.id,
            entry_type=LedgerEntryType.CREDIT,
            amount=amount,
            transaction_id=created_tx.id,
            balance_before=float(balance_before),
            balance_after=float(balance_after),
            description=f"Deposit reference {reference}"
        )
        await self.ledger_repo.create_ledger_entry(entry)

        return created_tx

    async def withdraw_funds(self, user_id: str, amount: float, reference: str) -> Transaction:
        # 1. Lock user's wallet
        wallet = await self.ledger_repo.get_wallet_by_user_id(user_id, lock=True)
        if not wallet:
            raise HTTPException(status_code=404, detail="Wallet not found")

        amt_decimal = Decimal(str(amount))
        balance_before = Decimal(str(wallet.balance))
        if balance_before < amt_decimal:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Insufficient funds in wallet"
            )

        balance_after = balance_before - amt_decimal

        # 2. Update wallet balance
        wallet.balance = float(balance_after)
        await self.ledger_repo.update_wallet(wallet)

        # 3. Create Transaction
        tx = Transaction(
            reference=reference,
            transaction_type=TransactionType.WITHDRAWAL,
            status=TransactionStatus.SUCCESS,
            amount=amount,
            fee=0.0,
            sender_wallet_id=wallet.id,
            description=f"Withdrawal of NGN {amount}"
        )
        created_tx = await self.ledger_repo.create_transaction(tx)

        # 4. Create Ledger Entry
        entry = WalletLedger(
            wallet_id=wallet.id,
            entry_type=LedgerEntryType.DEBIT,
            amount=amount,
            transaction_id=created_tx.id,
            balance_before=float(balance_before),
            balance_after=float(balance_after),
            description=f"Withdrawal reference {reference}"
        )
        await self.ledger_repo.create_ledger_entry(entry)

        return created_tx

    async def secure_escrow_payment(self, buyer_id: str, escrow: Escrow) -> Transaction:
        # Lock buyer wallet
        wallet = await self.ledger_repo.get_wallet_by_user_id(buyer_id, lock=True)
        if not wallet:
            raise HTTPException(status_code=404, detail="Buyer wallet not found")

        amt_decimal = Decimal(str(escrow.amount))
        balance_before = Decimal(str(wallet.balance))
        if balance_before < amt_decimal:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Insufficient wallet balance to secure escrow payment"
            )

        balance_after = balance_before - amt_decimal
        wallet.balance = float(balance_after)
        await self.ledger_repo.update_wallet(wallet)

        # Create Transaction
        ref = f"esc-pay-{escrow.id}-{uuid.uuid4().hex[:6]}"
        tx = Transaction(
            reference=ref,
            transaction_type=TransactionType.ESCROW_PAYMENT,
            status=TransactionStatus.SUCCESS,
            amount=float(amt_decimal),
            fee=0.0,
            sender_wallet_id=wallet.id,
            description=f"Secured payment for Order {escrow.order_id}"
        )
        created_tx = await self.ledger_repo.create_transaction(tx)

        # Create Ledger Entry
        entry = WalletLedger(
            wallet_id=wallet.id,
            entry_type=LedgerEntryType.DEBIT,
            amount=float(amt_decimal),
            transaction_id=created_tx.id,
            balance_before=float(balance_before),
            balance_after=float(balance_after),
            description=f"Locked funds for Escrow {escrow.id}"
        )
        await self.ledger_repo.create_ledger_entry(entry)

        return created_tx

    async def release_escrow_payout(self, escrow: Escrow) -> Transaction:
        # Payout amount = escrow.amount - escrow.fee
        payout_amt = Decimal(str(escrow.amount)) - Decimal(str(escrow.fee))
        if payout_amt < 0:
            payout_amt = Decimal("0.00")

        # Lock seller's wallet
        wallet = await self.ledger_repo.get_wallet_by_user_id(str(escrow.seller_id), lock=True)
        if not wallet:
            raise HTTPException(status_code=404, detail="Seller wallet not found")

        balance_before = Decimal(str(wallet.balance))
        balance_after = balance_before + payout_amt
        wallet.balance = float(balance_after)
        await self.ledger_repo.update_wallet(wallet)

        # Create Transaction
        ref = f"esc-rel-{escrow.id}-{uuid.uuid4().hex[:6]}"
        tx = Transaction(
            reference=ref,
            transaction_type=TransactionType.ESCROW_RELEASE,
            status=TransactionStatus.SUCCESS,
            amount=float(payout_amt),
            fee=float(escrow.fee),
            receiver_wallet_id=wallet.id,
            description=f"Escrow release payout for Order {escrow.order_id}"
        )
        created_tx = await self.ledger_repo.create_transaction(tx)

        # Create Ledger Entry
        entry = WalletLedger(
            wallet_id=wallet.id,
            entry_type=LedgerEntryType.CREDIT,
            amount=float(payout_amt),
            transaction_id=created_tx.id,
            balance_before=float(balance_before),
            balance_after=float(balance_after),
            description=f"Payout from Escrow {escrow.id} (fee deducted: {escrow.fee})"
        )
        await self.ledger_repo.create_ledger_entry(entry)

        return created_tx

    async def refund_escrow_payment(self, escrow: Escrow) -> Transaction:
        # Full refund to buyer
        refund_amt = Decimal(str(escrow.amount))

        # Lock buyer's wallet
        wallet = await self.ledger_repo.get_wallet_by_user_id(str(escrow.buyer_id), lock=True)
        if not wallet:
            raise HTTPException(status_code=404, detail="Buyer wallet not found")

        balance_before = Decimal(str(wallet.balance))
        balance_after = balance_before + refund_amt
        wallet.balance = float(balance_after)
        await self.ledger_repo.update_wallet(wallet)

        # Create Transaction
        ref = f"esc-ref-{escrow.id}-{uuid.uuid4().hex[:6]}"
        tx = Transaction(
            reference=ref,
            transaction_type=TransactionType.REFUND,
            status=TransactionStatus.SUCCESS,
            amount=float(refund_amt),
            fee=0.0,
            receiver_wallet_id=wallet.id,
            description=f"Refund from Escrow {escrow.id} for Order {escrow.order_id}"
        )
        created_tx = await self.ledger_repo.create_transaction(tx)

        # Create Ledger Entry
        entry = WalletLedger(
            wallet_id=wallet.id,
            entry_type=LedgerEntryType.CREDIT,
            amount=float(refund_amt),
            transaction_id=created_tx.id,
            balance_before=float(balance_before),
            balance_after=float(balance_after),
            description=f"Refunded from Escrow {escrow.id}"
        )
        await self.ledger_repo.create_ledger_entry(entry)

        return created_tx

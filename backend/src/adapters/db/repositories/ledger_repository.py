import uuid
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from src.domain.repositories.ledger_repository import LedgerRepositoryInterface
from src.adapters.db.models import Wallet, WalletLedger, Transaction, Payment

class SQLAlchemyLedgerRepository(LedgerRepositoryInterface):
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_wallet_by_user_id(self, user_id: str, lock: bool = False) -> Optional[Wallet]:
        uid = uuid.UUID(user_id) if isinstance(user_id, str) else user_id
        stmt = select(Wallet).where(Wallet.user_id == uid, Wallet.deleted_at.is_(None))
        if lock:
            stmt = stmt.with_for_update()
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_wallet_by_id(self, wallet_id: str, lock: bool = False) -> Optional[Wallet]:
        uid = uuid.UUID(wallet_id) if isinstance(wallet_id, str) else wallet_id
        stmt = select(Wallet).where(Wallet.id == uid, Wallet.deleted_at.is_(None))
        if lock:
            stmt = stmt.with_for_update()
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def create_wallet(self, wallet: Wallet) -> Wallet:
        self.db.add(wallet)
        await self.db.flush()
        return wallet

    async def update_wallet(self, wallet: Wallet) -> Wallet:
        self.db.add(wallet)
        await self.db.flush()
        return wallet

    async def create_transaction(self, transaction: Transaction) -> Transaction:
        self.db.add(transaction)
        await self.db.flush()
        return transaction

    async def update_transaction(self, transaction: Transaction) -> Transaction:
        self.db.add(transaction)
        await self.db.flush()
        return transaction

    async def get_transaction_by_id(self, transaction_id: str) -> Optional[Transaction]:
        uid = uuid.UUID(transaction_id) if isinstance(transaction_id, str) else transaction_id
        stmt = select(Transaction).where(Transaction.id == uid, Transaction.deleted_at.is_(None))
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_transaction_by_reference(self, reference: str) -> Optional[Transaction]:
        stmt = select(Transaction).where(Transaction.reference == reference, Transaction.deleted_at.is_(None))
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def create_ledger_entry(self, entry: WalletLedger) -> WalletLedger:
        self.db.add(entry)
        await self.db.flush()
        return entry

    async def get_ledger_entries(self, wallet_id: str, limit: int = 20) -> List[WalletLedger]:
        uid = uuid.UUID(wallet_id) if isinstance(wallet_id, str) else wallet_id
        stmt = select(WalletLedger).where(WalletLedger.wallet_id == uid).order_by(WalletLedger.created_at.desc()).limit(limit)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def create_payment(self, payment: Payment) -> Payment:
        self.db.add(payment)
        await self.db.flush()
        return payment

    async def get_payment_by_reference(self, reference: str) -> Optional[Payment]:
        stmt = select(Payment).where(Payment.provider_reference == reference, Payment.deleted_at.is_(None))
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def update_payment(self, payment: Payment) -> Payment:
        self.db.add(payment)
        await self.db.flush()
        return payment

from abc import ABC, abstractmethod
from typing import Optional, List
from src.adapters.db.models import Wallet, WalletLedger, Transaction, Payment

class LedgerRepositoryInterface(ABC):
    @abstractmethod
    async def get_wallet_by_user_id(self, user_id: str, lock: bool = False) -> Optional[Wallet]:
        pass

    @abstractmethod
    async def get_wallet_by_id(self, wallet_id: str, lock: bool = False) -> Optional[Wallet]:
        pass

    @abstractmethod
    async def create_wallet(self, wallet: Wallet) -> Wallet:
        pass

    @abstractmethod
    async def update_wallet(self, wallet: Wallet) -> Wallet:
        pass

    @abstractmethod
    async def create_transaction(self, transaction: Transaction) -> Transaction:
        pass

    @abstractmethod
    async def update_transaction(self, transaction: Transaction) -> Transaction:
        pass

    @abstractmethod
    async def get_transaction_by_id(self, transaction_id: str) -> Optional[Transaction]:
        pass

    @abstractmethod
    async def get_transaction_by_reference(self, reference: str) -> Optional[Transaction]:
        pass

    @abstractmethod
    async def create_ledger_entry(self, entry: WalletLedger) -> WalletLedger:
        pass

    @abstractmethod
    async def get_ledger_entries(self, wallet_id: str, limit: int = 20) -> List[WalletLedger]:
        pass

    @abstractmethod
    async def create_payment(self, payment: Payment) -> Payment:
        pass

    @abstractmethod
    async def get_payment_by_reference(self, reference: str) -> Optional[Payment]:
        pass

    @abstractmethod
    async def update_payment(self, payment: Payment) -> Payment:
        pass

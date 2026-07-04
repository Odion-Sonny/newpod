from abc import ABC, abstractmethod
from typing import Optional, List
from src.adapters.db.models import Product, Order, Escrow

class EscrowRepositoryInterface(ABC):
    @abstractmethod
    async def get_product_by_id(self, product_id: str) -> Optional[Product]:
        pass

    @abstractmethod
    async def list_products(self, skip: int = 0, limit: int = 10) -> List[Product]:
        pass

    @abstractmethod
    async def create_product(self, product: Product) -> Product:
        pass

    @abstractmethod
    async def get_order_by_id(self, order_id: str) -> Optional[Order]:
        pass

    @abstractmethod
    async def create_order(self, order: Order) -> Order:
        pass

    @abstractmethod
    async def get_escrow_by_id(self, escrow_id: str) -> Optional[Escrow]:
        pass

    @abstractmethod
    async def get_escrow_by_order_id(self, order_id: str) -> Optional[Escrow]:
        pass

    @abstractmethod
    async def create_escrow(self, escrow: Escrow) -> Escrow:
        pass

    @abstractmethod
    async def update_escrow(self, escrow: Escrow) -> Escrow:
        pass

    @abstractmethod
    async def update_order(self, order: Order) -> Order:
        pass

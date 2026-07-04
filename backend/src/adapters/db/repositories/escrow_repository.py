import uuid
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from src.domain.repositories.escrow_repository import EscrowRepositoryInterface
from src.adapters.db.models import Product, Order, Escrow

class SQLAlchemyEscrowRepository(EscrowRepositoryInterface):
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_product_by_id(self, product_id: str) -> Optional[Product]:
        uid = uuid.UUID(product_id) if isinstance(product_id, str) else product_id
        stmt = select(Product).where(Product.id == uid, Product.deleted_at.is_(None))
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_products(self, skip: int = 0, limit: int = 10) -> List[Product]:
        stmt = select(Product).where(Product.deleted_at.is_(None)).offset(skip).limit(limit)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def create_product(self, product: Product) -> Product:
        self.db.add(product)
        await self.db.flush()
        return product

    async def get_order_by_id(self, order_id: str) -> Optional[Order]:
        uid = uuid.UUID(order_id) if isinstance(order_id, str) else order_id
        stmt = (
            select(Order)
            .where(Order.id == uid, Order.deleted_at.is_(None))
            .options(selectinload(Order.items))
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def create_order(self, order: Order) -> Order:
        self.db.add(order)
        await self.db.flush()
        return order

    async def get_escrow_by_id(self, escrow_id: str) -> Optional[Escrow]:
        uid = uuid.UUID(escrow_id) if isinstance(escrow_id, str) else escrow_id
        stmt = (
            select(Escrow)
            .where(Escrow.id == uid, Escrow.deleted_at.is_(None))
            .options(
                selectinload(Escrow.order).selectinload(Order.items),
                selectinload(Escrow.order).selectinload(Order.courier_tracking)
            )
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_escrow_by_order_id(self, order_id: str) -> Optional[Escrow]:
        uid = uuid.UUID(order_id) if isinstance(order_id, str) else order_id
        stmt = (
            select(Escrow)
            .where(Escrow.order_id == uid, Escrow.deleted_at.is_(None))
            .options(
                selectinload(Escrow.order).selectinload(Order.items),
                selectinload(Escrow.order).selectinload(Order.courier_tracking)
            )
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def create_escrow(self, escrow: Escrow) -> Escrow:
        self.db.add(escrow)
        await self.db.flush()
        return escrow

    async def update_escrow(self, escrow: Escrow) -> Escrow:
        self.db.add(escrow)
        await self.db.flush()
        return escrow

    async def update_order(self, order: Order) -> Order:
        self.db.add(order)
        await self.db.flush()
        return order

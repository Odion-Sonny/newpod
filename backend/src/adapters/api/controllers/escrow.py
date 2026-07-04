from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional

from src.core.database import get_db
from src.adapters.db.repositories.escrow_repository import SQLAlchemyEscrowRepository
from src.use_cases.escrow import EscrowService
from src.adapters.api.schemas.escrow import (
    ProductCreate, ProductResponse, OrderCreate, OrderResponse,
    EscrowResponse, AddressCreate, AddressResponse
)
from src.adapters.api.dependencies import get_current_user, get_current_user_optional
from src.adapters.db.models import User, Address

from src.adapters.db.repositories.ledger_repository import SQLAlchemyLedgerRepository
from src.use_cases.ledger import LedgerService

router = APIRouter()

def get_escrow_service(db: AsyncSession = Depends(get_db)) -> EscrowService:
    escrow_repo = SQLAlchemyEscrowRepository(db)
    ledger_repo = SQLAlchemyLedgerRepository(db)
    ledger_service = LedgerService(ledger_repo)
    return EscrowService(escrow_repo, ledger_service)

# --- Products ---

@router.post("/products", response_model=ProductResponse, status_code=status.HTTP_201_CREATED)
async def create_product(
    data: ProductCreate,
    current_user: User = Depends(get_current_user),
    service: EscrowService = Depends(get_escrow_service)
):
    product = await service.create_product(str(current_user.id), data)
    return product

@router.get("/products", response_model=List[ProductResponse])
async def list_products(
    skip: int = 0,
    limit: int = 10,
    service: EscrowService = Depends(get_escrow_service)
):
    return await service.list_products(skip=skip, limit=limit)

# --- Addresses ---

@router.post("/addresses", response_model=AddressResponse, status_code=status.HTTP_201_CREATED)
async def create_address(
    data: AddressCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    address = Address(
        user_id=current_user.id,
        street=data.street,
        city=data.city,
        state=data.state,
        country=data.country,
        postal_code=data.postal_code,
        is_default=data.is_default
    )
    db.add(address)
    await db.commit()
    await db.refresh(address)
    return address

@router.get("/addresses", response_model=List[AddressResponse])
async def list_addresses(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    from sqlalchemy.future import select
    stmt = select(Address).where(Address.user_id == current_user.id, Address.deleted_at.is_(None))
    result = await db.execute(stmt)
    return list(result.scalars().all())

# --- Orders & Escrow Creation ---

@router.post("/orders", response_model=OrderResponse, status_code=status.HTTP_201_CREATED)
async def create_order(
    data: OrderCreate,
    current_user: User = Depends(get_current_user),
    service: EscrowService = Depends(get_escrow_service)
):
    order, escrow = await service.create_order_and_escrow(str(current_user.id), data)
    return order

# --- Escrow Transitions ---

@router.get("/escrows/{escrow_id}", response_model=EscrowResponse)
async def get_escrow(
    escrow_id: str,
    service: EscrowService = Depends(get_escrow_service)
):
    escrow_repo = service.escrow_repo
    escrow = await escrow_repo.get_escrow_by_id(escrow_id)
    if not escrow:
        raise HTTPException(status_code=404, detail="Escrow not found")
    return escrow

@router.get("/escrows/order/{order_id}", response_model=EscrowResponse)
async def get_escrow_by_order(
    order_id: str,
    service: EscrowService = Depends(get_escrow_service)
):
    escrow_repo = service.escrow_repo
    escrow = await escrow_repo.get_escrow_by_order_id(order_id)
    if not escrow:
        raise HTTPException(status_code=404, detail="Escrow not found for this order")
    return escrow

@router.post("/escrows/{escrow_id}/secure-payment", response_model=EscrowResponse)
async def secure_payment(
    escrow_id: str,
    current_user: Optional[User] = Depends(get_current_user_optional),
    service: EscrowService = Depends(get_escrow_service)
):
    buyer_id = str(current_user.id) if current_user else None
    return await service.secure_payment(escrow_id, buyer_id)

@router.post("/escrows/{escrow_id}/accept", response_model=EscrowResponse)
async def accept_order(
    escrow_id: str,
    current_user: User = Depends(get_current_user),
    service: EscrowService = Depends(get_escrow_service)
):
    return await service.accept_order(escrow_id, str(current_user.id))

@router.post("/escrows/{escrow_id}/pack", response_model=EscrowResponse)
async def pack_order(
    escrow_id: str,
    current_user: User = Depends(get_current_user),
    service: EscrowService = Depends(get_escrow_service)
):
    return await service.pack_order(escrow_id, str(current_user.id))

@router.post("/escrows/{escrow_id}/ship", response_model=EscrowResponse)
async def ship_order(
    escrow_id: str,
    tracking_number: str,
    courier_provider: str,
    current_user: User = Depends(get_current_user),
    service: EscrowService = Depends(get_escrow_service)
):
    return await service.ship_order(
        escrow_id, str(current_user.id), tracking_number, courier_provider
    )

@router.post("/escrows/{escrow_id}/deliver", response_model=EscrowResponse)
async def deliver_order(
    escrow_id: str,
    service: EscrowService = Depends(get_escrow_service)
):
    return await service.deliver_order(escrow_id)

@router.post("/escrows/{escrow_id}/release", response_model=EscrowResponse)
async def release_escrow(
    escrow_id: str,
    current_user: User = Depends(get_current_user),
    service: EscrowService = Depends(get_escrow_service)
):
    # Determine if user is admin
    user_roles = [role.name for role in current_user.roles]
    is_admin = "ADMIN" in user_roles
    return await service.release_escrow(escrow_id, str(current_user.id), is_admin=is_admin)

@router.post("/escrows/{escrow_id}/cancel", response_model=EscrowResponse)
async def cancel_escrow(
    escrow_id: str,
    current_user: User = Depends(get_current_user),
    service: EscrowService = Depends(get_escrow_service)
):
    return await service.cancel_escrow(escrow_id, str(current_user.id))

@router.post("/escrows/{escrow_id}/dispute", response_model=EscrowResponse)
async def dispute_escrow(
    escrow_id: str,
    reason: str,
    current_user: User = Depends(get_current_user),
    service: EscrowService = Depends(get_escrow_service)
):
    return await service.dispute_escrow(escrow_id, str(current_user.id), reason)

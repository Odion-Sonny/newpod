import uuid
from datetime import datetime, timezone
from typing import List, Optional, Tuple
from fastapi import HTTPException, status
from src.domain.repositories.escrow_repository import EscrowRepositoryInterface
from src.adapters.db.models import (
    Product, Order, OrderItem, Escrow, EscrowStatus,
    Address, CourierTracking
)
from src.adapters.api.schemas.escrow import ProductCreate, OrderCreate, AddressCreate

def calculate_escrow_fee(amount: float) -> float:
    # 1.5% platform fee, capped at 2000 NGN
    fee = amount * 0.015
    return round(min(fee, 2000.0), 2)

class EscrowService:
    def __init__(self, escrow_repo: EscrowRepositoryInterface, ledger_service = None):
        self.escrow_repo = escrow_repo
        self.ledger_service = ledger_service

    async def create_product(self, seller_id: str, data: ProductCreate) -> Product:
        seller_uuid = uuid.UUID(seller_id) if isinstance(seller_id, str) else seller_id
        product = Product(
            seller_id=seller_uuid,
            title=data.title,
            description=data.description,
            price=data.price,
            stock=data.stock,
            images=data.images,
            is_active=True
        )
        return await self.escrow_repo.create_product(product)

    async def list_products(self, skip: int = 0, limit: int = 10) -> List[Product]:
        return await self.escrow_repo.list_products(skip=skip, limit=limit)

    async def create_order_and_escrow(self, buyer_id: str, data: OrderCreate) -> Tuple[Order, Escrow]:
        # Check that buyer is not seller
        buyer_uuid = uuid.UUID(buyer_id) if isinstance(buyer_id, str) else buyer_id
        if buyer_uuid == data.seller_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="You cannot buy your own product"
            )

        # Create Order Items and calculate total
        total_amount = 0.0
        order_items = []
        for item in data.items:
            product = await self.escrow_repo.get_product_by_id(str(item.product_id))
            if not product or not product.is_active:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Product {item.product_id} not found"
                )
            
            if product.stock < item.quantity:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Insufficient stock for product '{product.title}'"
                )
            
            # Deduct stock
            product.stock -= item.quantity
            # (In a real DB, SQLAlchemy tracks changes and flushes them)
            
            item_price = float(product.price) * item.quantity
            total_amount += item_price

            order_item = OrderItem(
                product_id=product.id,
                quantity=item.quantity,
                price=float(product.price)
            )
            order_items.append(order_item)

        # Create Order
        new_order = Order(
            buyer_id=buyer_uuid,
            seller_id=data.seller_id,
            total_amount=total_amount,
            status="pending",
            delivery_address_id=data.delivery_address_id,
            items=order_items
        )
        created_order = await self.escrow_repo.create_order(new_order)

        # Create associated Escrow
        platform_fee = calculate_escrow_fee(total_amount)
        new_escrow = Escrow(
            buyer_id=buyer_uuid,
            seller_id=data.seller_id,
            order_id=created_order.id,
            amount=total_amount,
            fee=platform_fee,
            status=EscrowStatus.CREATED
        )
        created_escrow = await self.escrow_repo.create_escrow(new_escrow)

        return created_order, created_escrow

    # --- Escrow State Machine transitions ---
    
    async def secure_payment(self, escrow_id: str, buyer_id: Optional[str] = None) -> Escrow:
        escrow = await self.escrow_repo.get_escrow_by_id(escrow_id)
        if not escrow:
            raise HTTPException(status_code=404, detail="Escrow not found")
        
        # Valid start states
        if escrow.status not in [EscrowStatus.CREATED, EscrowStatus.PENDING_PAYMENT]:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot secure payment from escrow status: {escrow.status.value}"
            )
            
        if buyer_id and self.ledger_service:
            await self.ledger_service.secure_escrow_payment(buyer_id, escrow)
            
        escrow.status = EscrowStatus.PAYMENT_SECURED
        escrow.order.status = "payment_secured"
        return await self.escrow_repo.update_escrow(escrow)

    async def accept_order(self, escrow_id: str, seller_id: str) -> Escrow:
        escrow = await self.escrow_repo.get_escrow_by_id(escrow_id)
        if not escrow:
            raise HTTPException(status_code=404, detail="Escrow not found")
            
        seller_uuid = uuid.UUID(seller_id) if isinstance(seller_id, str) else seller_id
        if escrow.seller_id != seller_uuid:
            raise HTTPException(status_code=403, detail="Only the seller can accept this order")
            
        if escrow.status != EscrowStatus.PAYMENT_SECURED:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot accept order in status: {escrow.status.value}"
            )
            
        escrow.status = EscrowStatus.SELLER_ACCEPTED
        escrow.order.status = "accepted"
        return await self.escrow_repo.update_escrow(escrow)

    async def pack_order(self, escrow_id: str, seller_id: str) -> Escrow:
        escrow = await self.escrow_repo.get_escrow_by_id(escrow_id)
        if not escrow:
            raise HTTPException(status_code=404, detail="Escrow not found")
            
        seller_uuid = uuid.UUID(seller_id) if isinstance(seller_id, str) else seller_id
        if escrow.seller_id != seller_uuid:
            raise HTTPException(status_code=403, detail="Only the seller can pack this order")
            
        if escrow.status != EscrowStatus.SELLER_ACCEPTED:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot pack order in status: {escrow.status.value}"
            )
            
        escrow.status = EscrowStatus.PACKED
        escrow.order.status = "packed"
        return await self.escrow_repo.update_escrow(escrow)

    async def ship_order(self, escrow_id: str, seller_id: str, tracking_number: str, courier_provider: str) -> Escrow:
        escrow = await self.escrow_repo.get_escrow_by_id(escrow_id)
        if not escrow:
            raise HTTPException(status_code=404, detail="Escrow not found")
            
        seller_uuid = uuid.UUID(seller_id) if isinstance(seller_id, str) else seller_id
        if escrow.seller_id != seller_uuid:
            raise HTTPException(status_code=403, detail="Only the seller can ship this order")
            
        if escrow.status != EscrowStatus.PACKED:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot ship order in status: {escrow.status.value}"
            )
            
        # Create courier tracking record
        tracking = CourierTracking(
            order_id=escrow.order_id,
            courier_provider=courier_provider,
            tracking_number=tracking_number,
            current_status="shipped",
            status_updates=[{
                "status": "shipped",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "description": "Item Shipped by Seller"
            }]
        )
        escrow.order.courier_tracking = tracking
        escrow.status = EscrowStatus.SHIPPED
        escrow.order.status = "shipped"
        return await self.escrow_repo.update_escrow(escrow)

    async def deliver_order(self, escrow_id: str) -> Escrow:
        escrow = await self.escrow_repo.get_escrow_by_id(escrow_id)
        if not escrow:
            raise HTTPException(status_code=404, detail="Escrow not found")
            
        if escrow.status not in [EscrowStatus.SHIPPED, EscrowStatus.OUT_FOR_DELIVERY]:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot mark as delivered from status: {escrow.status.value}"
            )
            
        escrow.status = EscrowStatus.DELIVERED
        escrow.order.status = "delivered"
        if escrow.order.courier_tracking:
            escrow.order.courier_tracking.current_status = "delivered"
            escrow.order.courier_tracking.status_updates.append({
                "status": "delivered",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "description": "Item Delivered to Buyer"
            })
            
        # Transition immediately to inspection window
        escrow.status = EscrowStatus.INSPECTION_WINDOW
        return await self.escrow_repo.update_escrow(escrow)

    async def release_escrow(self, escrow_id: str, user_id: str, is_admin: bool = False) -> Escrow:
        escrow = await self.escrow_repo.get_escrow_by_id(escrow_id)
        if not escrow:
            raise HTTPException(status_code=404, detail="Escrow not found")
            
        user_uuid = uuid.UUID(user_id) if isinstance(user_id, str) else user_id
        if not is_admin and escrow.buyer_id != user_uuid:
            raise HTTPException(status_code=403, detail="Only the buyer or admin can release funds")
            
        if escrow.status not in [EscrowStatus.INSPECTION_WINDOW, EscrowStatus.DELIVERED]:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot release funds from status: {escrow.status.value}"
            )
            
        escrow.status = EscrowStatus.RELEASED
        escrow.order.status = "completed"
        
        if self.ledger_service:
            await self.ledger_service.release_escrow_payout(escrow)
            
        return await self.escrow_repo.update_escrow(escrow)

    async def cancel_escrow(self, escrow_id: str, user_id: str) -> Escrow:
        escrow = await self.escrow_repo.get_escrow_by_id(escrow_id)
        if not escrow:
            raise HTTPException(status_code=404, detail="Escrow not found")
            
        user_uuid = uuid.UUID(user_id) if isinstance(user_id, str) else user_id
        
        # Cancellation rules:
        # 1. Buyer can cancel if payment is not secured (CREATED or PENDING_PAYMENT)
        # 2. Seller can cancel at any time before shipping (payment secured, accepted, packed), returning funds to buyer.
        if escrow.status in [EscrowStatus.CREATED, EscrowStatus.PENDING_PAYMENT]:
            if escrow.buyer_id != user_uuid:
                raise HTTPException(status_code=403, detail="Only the buyer can cancel an unpaid escrow")
        elif escrow.status in [EscrowStatus.PAYMENT_SECURED, EscrowStatus.SELLER_ACCEPTED, EscrowStatus.PACKED]:
            if escrow.seller_id != user_uuid:
                raise HTTPException(status_code=403, detail="Only the seller can cancel a secured escrow before shipping")
        else:
            raise HTTPException(status_code=400, detail="Cannot cancel escrow at this stage")
            
        # Refund if payment was secured
        if escrow.status in [EscrowStatus.PAYMENT_SECURED, EscrowStatus.SELLER_ACCEPTED, EscrowStatus.PACKED]:
            if self.ledger_service:
                await self.ledger_service.refund_escrow_payment(escrow)

        escrow.status = EscrowStatus.CANCELLED
        escrow.order.status = "cancelled"
        
        # Restore stock
        for item in escrow.order.items:
            product = await self.escrow_repo.get_product_by_id(str(item.product_id))
            if product:
                product.stock += item.quantity
                
        return await self.escrow_repo.update_escrow(escrow)

    async def dispute_escrow(self, escrow_id: str, buyer_id: str, reason: str) -> Escrow:
        escrow = await self.escrow_repo.get_escrow_by_id(escrow_id)
        if not escrow:
            raise HTTPException(status_code=404, detail="Escrow not found")
            
        buyer_uuid = uuid.UUID(buyer_id) if isinstance(buyer_id, str) else buyer_id
        if escrow.buyer_id != buyer_uuid:
            raise HTTPException(status_code=403, detail="Only the buyer can open a dispute")
            
        # Can only dispute once items are shipped, delivered, or in inspection window
        if escrow.status not in [EscrowStatus.SHIPPED, EscrowStatus.DELIVERED, EscrowStatus.INSPECTION_WINDOW]:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot open dispute in status: {escrow.status.value}"
            )
            
        escrow.status = EscrowStatus.DISPUTED
        escrow.order.status = "disputed"
        
        # (Dispute record creation will be handled in Milestone 5)
        
        return await self.escrow_repo.update_escrow(escrow)

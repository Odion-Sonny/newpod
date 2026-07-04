import uuid
from typing import List, Optional
from pydantic import BaseModel, Field
from src.adapters.db.models import EscrowStatus

class ProductCreate(BaseModel):
    title: str = Field(..., min_length=3, max_length=255)
    description: str = Field(..., min_length=10)
    price: float = Field(..., gt=0)
    stock: int = Field(default=1, ge=1)
    images: List[str] = Field(default_factory=list)

class ProductResponse(BaseModel):
    id: uuid.UUID
    title: str
    description: str
    price: float
    stock: int
    images: List[str]
    seller_id: uuid.UUID

    model_config = {
        "from_attributes": True
    }

class OrderItemCreate(BaseModel):
    product_id: uuid.UUID
    quantity: int = Field(default=1, ge=1)

class OrderCreate(BaseModel):
    seller_id: uuid.UUID
    items: List[OrderItemCreate]
    delivery_address_id: uuid.UUID

class OrderItemResponse(BaseModel):
    id: uuid.UUID
    product_id: uuid.UUID
    quantity: int
    price: float

    model_config = {
        "from_attributes": True
    }

class OrderResponse(BaseModel):
    id: uuid.UUID
    buyer_id: uuid.UUID
    seller_id: uuid.UUID
    total_amount: float
    status: str
    delivery_address_id: uuid.UUID
    items: List[OrderItemResponse] = []

    model_config = {
        "from_attributes": True
    }

class EscrowResponse(BaseModel):
    id: uuid.UUID
    buyer_id: uuid.UUID
    seller_id: uuid.UUID
    order_id: uuid.UUID
    amount: float
    fee: float
    status: EscrowStatus

    model_config = {
        "from_attributes": True
    }

class AddressCreate(BaseModel):
    street: str
    city: str
    state: str
    country: str = "Nigeria"
    postal_code: Optional[str] = None
    is_default: bool = False

class AddressResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    street: str
    city: str
    state: str
    country: str
    postal_code: Optional[str]
    is_default: bool

    model_config = {
        "from_attributes": True
    }

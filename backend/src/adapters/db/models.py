import uuid
from datetime import datetime, timezone
from typing import List, Optional, Any
from enum import Enum as PyEnum
from sqlalchemy import (
    String, ForeignKey, Text, Numeric, Boolean, DateTime,
    Table, Column, Enum, JSON, Index, UniqueConstraint
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.core.database import Base

# Enums
class KYCLevel(str, PyEnum):
    TIER_0 = "TIER_0"
    TIER_1 = "TIER_1"
    TIER_2 = "TIER_2"
    TIER_3 = "TIER_3"

class EscrowStatus(str, PyEnum):
    CREATED = "CREATED"
    PENDING_PAYMENT = "PENDING_PAYMENT"
    PAYMENT_SECURED = "PAYMENT_SECURED"
    SELLER_ACCEPTED = "SELLER_ACCEPTED"
    PACKED = "PACKED"
    SHIPPED = "SHIPPED"
    OUT_FOR_DELIVERY = "OUT_FOR_DELIVERY"
    DELIVERED = "DELIVERED"
    INSPECTION_WINDOW = "INSPECTION_WINDOW"
    RELEASED = "RELEASED"
    REFUNDED = "REFUNDED"
    CANCELLED = "CANCELLED"
    DISPUTED = "DISPUTED"
    RESOLVED = "RESOLVED"
    EXPIRED = "EXPIRED"

class LedgerEntryType(str, PyEnum):
    DEBIT = "DEBIT"
    CREDIT = "CREDIT"

class TransactionType(str, PyEnum):
    ESCROW_PAYMENT = "ESCROW_PAYMENT"
    ESCROW_RELEASE = "ESCROW_RELEASE"
    SETTLEMENT = "SETTLEMENT"
    REFUND = "REFUND"
    DEPOSIT = "DEPOSIT"
    WITHDRAWAL = "WITHDRAWAL"

class TransactionStatus(str, PyEnum):
    PENDING = "PENDING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"

class WalletStatus(str, PyEnum):
    ACTIVE = "ACTIVE"
    FROZEN = "FROZEN"

class DisputeStatus(str, PyEnum):
    OPEN = "OPEN"
    UNDER_INVESTIGATION = "UNDER_INVESTIGATION"
    RESOLVED = "RESOLVED"
    CANCELLED = "CANCELLED"

class EvidenceType(str, PyEnum):
    PHOTO = "PHOTO"
    VIDEO = "VIDEO"
    DOCUMENT = "DOCUMENT"

class NotificationStatus(str, PyEnum):
    PENDING = "PENDING"
    SENT = "SENT"
    FAILED = "FAILED"
    READ = "READ"

class NotificationType(str, PyEnum):
    EMAIL = "EMAIL"
    SMS = "SMS"
    PUSH = "PUSH"
    IN_APP = "IN_APP"

# Association Tables
user_roles = Table(
    "user_roles",
    Base.metadata,
    Column("user_id", ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("role_id", ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
)

role_permissions = Table(
    "role_permissions",
    Base.metadata,
    Column("role_id", ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
    Column("permission_id", ForeignKey("permissions.id", ondelete="CASCADE"), primary_key=True),
)

# Core Models
class TimeStampedBase:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

class User(Base, TimeStampedBase):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    phone: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    
    # Verification & KYC
    bvn_hash: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    nin_hash: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    face_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    kyc_level: Mapped[KYCLevel] = mapped_column(Enum(KYCLevel), default=KYCLevel.TIER_0)
    
    # Trust & Risk Score
    trust_score: Mapped[float] = mapped_column(Numeric(5, 2), default=100.0)
    dispute_ratio: Mapped[float] = mapped_column(Numeric(5, 2), default=0.0)
    transaction_volume: Mapped[float] = mapped_column(Numeric(15, 2), default=0.0)
    fraud_score: Mapped[float] = mapped_column(Numeric(5, 2), default=0.0)

    # Relationships
    roles: Mapped[List["Role"]] = relationship(secondary=user_roles, back_populates="users")
    wallet: Mapped[Optional["Wallet"]] = relationship(back_populates="user", uselist=False)
    addresses: Mapped[List["Address"]] = relationship(back_populates="user")
    sessions: Mapped[List["Session"]] = relationship(back_populates="user")
    refresh_tokens: Mapped[List["RefreshToken"]] = relationship(back_populates="user")
    api_keys: Mapped[List["APIKey"]] = relationship(back_populates="user")
    audit_logs: Mapped[List["AuditLog"]] = relationship(back_populates="user")
    admin_notes_about: Mapped[List["AdminNote"]] = relationship(
        back_populates="target_user", foreign_keys="[AdminNote.target_user_id]"
    )

class Role(Base, TimeStampedBase):
    __tablename__ = "roles"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(100), unique=True, index=True)

    users: Mapped[List["User"]] = relationship(secondary=user_roles, back_populates="roles")
    permissions: Mapped[List["Permission"]] = relationship(
        secondary=role_permissions, back_populates="roles"
    )

class Permission(Base, TimeStampedBase):
    __tablename__ = "permissions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(100), unique=True, index=True)

    roles: Mapped[List["Role"]] = relationship(secondary=role_permissions, back_populates="permissions")

class Wallet(Base, TimeStampedBase):
    __tablename__ = "wallets"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True)
    balance: Mapped[float] = mapped_column(Numeric(15, 2), default=0.0)
    currency: Mapped[str] = mapped_column(String(10), default="NGN")
    status: Mapped[WalletStatus] = mapped_column(Enum(WalletStatus), default=WalletStatus.ACTIVE)

    user: Mapped["User"] = relationship(back_populates="wallet")
    ledger_entries: Mapped[List["WalletLedger"]] = relationship(back_populates="wallet")

class WalletLedger(Base):
    __tablename__ = "wallet_ledger"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    wallet_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("wallets.id", ondelete="CASCADE"), index=True)
    entry_type: Mapped[LedgerEntryType] = mapped_column(Enum(LedgerEntryType))
    amount: Mapped[float] = mapped_column(Numeric(15, 2))
    transaction_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("transactions.id"), index=True)
    balance_before: Mapped[float] = mapped_column(Numeric(15, 2))
    balance_after: Mapped[float] = mapped_column(Numeric(15, 2))
    description: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True
    )

    wallet: Mapped["Wallet"] = relationship(back_populates="ledger_entries")
    transaction: Mapped["Transaction"] = relationship(foreign_keys=[transaction_id])

class Transaction(Base, TimeStampedBase):
    __tablename__ = "transactions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    reference: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    transaction_type: Mapped[TransactionType] = mapped_column(Enum(TransactionType))
    status: Mapped[TransactionStatus] = mapped_column(Enum(TransactionStatus), default=TransactionStatus.PENDING)
    amount: Mapped[float] = mapped_column(Numeric(15, 2))
    fee: Mapped[float] = mapped_column(Numeric(15, 2), default=0.0)
    
    sender_wallet_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("wallets.id"), nullable=True)
    receiver_wallet_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("wallets.id"), nullable=True)
    description: Mapped[str] = mapped_column(String(255))

class Product(Base, TimeStampedBase):
    __tablename__ = "products"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    seller_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text)
    price: Mapped[float] = mapped_column(Numeric(15, 2))
    stock: Mapped[int] = mapped_column(default=1)
    images: Mapped[Any] = mapped_column(JSON, default=list)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

class Order(Base, TimeStampedBase):
    __tablename__ = "orders"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    buyer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    seller_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    total_amount: Mapped[float] = mapped_column(Numeric(15, 2))
    status: Mapped[str] = mapped_column(String(50), default="pending")
    delivery_address_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("addresses.id"))
    
    items: Mapped[List["OrderItem"]] = relationship(back_populates="order")
    escrow: Mapped[Optional["Escrow"]] = relationship(back_populates="order", uselist=False)
    courier_tracking: Mapped[Optional["CourierTracking"]] = relationship(back_populates="order", uselist=False)

class OrderItem(Base, TimeStampedBase):
    __tablename__ = "order_items"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"), index=True)
    product_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("products.id"), index=True)
    quantity: Mapped[int] = mapped_column(default=1)
    price: Mapped[float] = mapped_column(Numeric(15, 2))

    order: Mapped["Order"] = relationship(back_populates="items")

class Escrow(Base, TimeStampedBase):
    __tablename__ = "escrows"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    buyer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    seller_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orders.id"), unique=True)
    amount: Mapped[float] = mapped_column(Numeric(15, 2))
    fee: Mapped[float] = mapped_column(Numeric(15, 2))
    status: Mapped[EscrowStatus] = mapped_column(Enum(EscrowStatus), default=EscrowStatus.CREATED)

    order: Mapped["Order"] = relationship(back_populates="escrow")
    payments: Mapped[List["Payment"]] = relationship(back_populates="escrow")
    disputes: Mapped[List["Dispute"]] = relationship(back_populates="escrow")

class Payment(Base, TimeStampedBase):
    __tablename__ = "payments"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    escrow_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("escrows.id", ondelete="CASCADE"), index=True, nullable=True)
    amount: Mapped[float] = mapped_column(Numeric(15, 2))
    provider: Mapped[str] = mapped_column(String(50), default="PAYSTACK")
    provider_reference: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    status: Mapped[str] = mapped_column(String(50), default="pending")
    paid_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    escrow: Mapped["Escrow"] = relationship(back_populates="payments")
    events: Mapped[List["PaymentEvent"]] = relationship(back_populates="payment")

class PaymentEvent(Base):
    __tablename__ = "payment_events"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    payment_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("payments.id", ondelete="CASCADE"), index=True)
    raw_payload: Mapped[Any] = mapped_column(JSON)
    event_type: Mapped[str] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    payment: Mapped["Payment"] = relationship(back_populates="events")

class Dispute(Base, TimeStampedBase):
    __tablename__ = "disputes"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    escrow_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("escrows.id", ondelete="CASCADE"), index=True)
    raised_by_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    status: Mapped[DisputeStatus] = mapped_column(Enum(DisputeStatus), default=DisputeStatus.OPEN)
    reason: Mapped[str] = mapped_column(Text)
    resolution_details: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    admin_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    escrow: Mapped["Escrow"] = relationship(back_populates="disputes")
    evidence: Mapped[List["Evidence"]] = relationship(back_populates="dispute")
    timeline_logs: Mapped[List["DisputeTimeline"]] = relationship(back_populates="dispute")

class Evidence(Base, TimeStampedBase):
    __tablename__ = "evidence"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    dispute_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("disputes.id", ondelete="CASCADE"), index=True)
    uploaded_by_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    file_url: Mapped[str] = mapped_column(String(512))
    file_type: Mapped[EvidenceType] = mapped_column(Enum(EvidenceType))
    hash: Mapped[str] = mapped_column(String(64))  # For tamper detection

    dispute: Mapped["Dispute"] = relationship(back_populates="evidence")

class DisputeTimeline(Base):
    __tablename__ = "dispute_timeline"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    dispute_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("disputes.id", ondelete="CASCADE"), index=True)
    event_type: Mapped[str] = mapped_column(String(100))
    description: Mapped[str] = mapped_column(Text)
    metadata_json: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    dispute: Mapped["Dispute"] = relationship(back_populates="timeline_logs")

class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    participant1_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    participant2_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    messages: Mapped[List["Message"]] = relationship(back_populates="conversation")

class Message(Base, TimeStampedBase):
    __tablename__ = "messages"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    conversation_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("conversations.id", ondelete="CASCADE"), index=True)
    sender_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    content: Mapped[str] = mapped_column(Text)
    attachment_url: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    read_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    conversation: Mapped["Conversation"] = relationship(back_populates="messages")

class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    type: Mapped[NotificationType] = mapped_column(Enum(NotificationType))
    title: Mapped[str] = mapped_column(String(255))
    body: Mapped[str] = mapped_column(Text)
    status: Mapped[NotificationStatus] = mapped_column(Enum(NotificationStatus), default=NotificationStatus.PENDING)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True
    )

class Review(Base, TimeStampedBase):
    __tablename__ = "reviews"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    reviewer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    reviewee_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    escrow_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("escrows.id"), index=True)
    rating: Mapped[int] = mapped_column(default=5)
    comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

class Address(Base, TimeStampedBase):
    __tablename__ = "addresses"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    street: Mapped[str] = mapped_column(String(255))
    city: Mapped[str] = mapped_column(String(100))
    state: Mapped[str] = mapped_column(String(100))
    country: Mapped[str] = mapped_column(String(100), default="Nigeria")
    postal_code: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)

    user: Mapped["User"] = relationship(back_populates="addresses")

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    action: Mapped[str] = mapped_column(String(255))
    ip_address: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    details: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True
    )

    user: Mapped[Optional["User"]] = relationship(back_populates="audit_logs")

class Session(Base, TimeStampedBase):
    __tablename__ = "sessions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    ip_address: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    user: Mapped["User"] = relationship(back_populates="sessions")

class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    is_revoked: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    user: Mapped["User"] = relationship(back_populates="refresh_tokens")

class FraudEvent(Base):
    __tablename__ = "fraud_events"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    event_type: Mapped[str] = mapped_column(String(100))
    risk_score: Mapped[float] = mapped_column(Numeric(5, 2))
    details: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True
    )

class RiskScore(Base):
    __tablename__ = "risk_scores"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    score: Mapped[float] = mapped_column(Numeric(5, 2))
    evaluation_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    factors: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)

class CourierTracking(Base, TimeStampedBase):
    __tablename__ = "courier_tracking"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"), unique=True)
    courier_provider: Mapped[str] = mapped_column(String(100))
    tracking_number: Mapped[str] = mapped_column(String(100), index=True)
    status_updates: Mapped[Any] = mapped_column(JSON, default=list)
    current_status: Mapped[str] = mapped_column(String(100))

    order: Mapped["Order"] = relationship(back_populates="courier_tracking")

class APIKey(Base, TimeStampedBase):
    __tablename__ = "api_keys"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    key_hash: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(100))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped["User"] = relationship(back_populates="api_keys")

class AdminNote(Base, TimeStampedBase):
    __tablename__ = "admin_notes"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    target_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    admin_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    content: Mapped[str] = mapped_column(Text)

    target_user: Mapped["User"] = relationship(
        back_populates="admin_notes_about", foreign_keys=[target_user_id]
    )

class UserSetting(Base, TimeStampedBase):
    __tablename__ = "settings"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    key: Mapped[str] = mapped_column(String(100), index=True)
    value: Mapped[str] = mapped_column(String(255))

class SystemConfig(Base, TimeStampedBase):
    __tablename__ = "system_config"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    key: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    value: Mapped[str] = mapped_column(String(255))
    description: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

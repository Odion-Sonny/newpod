import uuid
from datetime import datetime
from pydantic import BaseModel, Field
from src.adapters.db.models import LedgerEntryType, WalletStatus

class DepositRequest(BaseModel):
    amount: float = Field(..., gt=100.0, description="Amount to deposit in NGN. Minimum 100 NGN.")

class DepositResponse(BaseModel):
    authorization_url: str
    reference: str

class WithdrawalRequest(BaseModel):
    amount: float = Field(..., gt=100.0)
    bank_code: str = Field(..., min_length=3, max_length=10)
    account_number: str = Field(..., min_length=10, max_length=10)
    recipient_name: str

class WalletResponse(BaseModel):
    id: uuid.UUID
    balance: float
    currency: str
    status: WalletStatus

    model_config = {
        "from_attributes": True
    }

class WalletLedgerResponse(BaseModel):
    id: uuid.UUID
    entry_type: LedgerEntryType
    amount: float
    balance_before: float
    balance_after: float
    description: str
    created_at: datetime

    model_config = {
        "from_attributes": True
    }

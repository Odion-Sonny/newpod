import uuid
from datetime import datetime
from typing import List, Optional, Any
from pydantic import BaseModel, Field

class DisputeRaiseRequest(BaseModel):
    escrow_id: uuid.UUID
    reason: str = Field(..., min_length=10)

class DisputeResolveRequest(BaseModel):
    verdict: str = Field(..., pattern="^(REFUND_BUYER|PAY_SELLER)$")
    resolution_details: str = Field(..., min_length=10)

class DisputeTimelineResponse(BaseModel):
    id: uuid.UUID
    dispute_id: uuid.UUID
    event_type: str
    description: str
    metadata_json: Optional[Any] = None
    created_at: datetime

    model_config = {
        "from_attributes": True
    }

class EvidenceResponse(BaseModel):
    id: uuid.UUID
    dispute_id: uuid.UUID
    uploaded_by_user_id: uuid.UUID
    file_url: str
    file_type: str
    hash: str
    created_at: datetime

    model_config = {
        "from_attributes": True
    }

class DisputeResponse(BaseModel):
    id: uuid.UUID
    escrow_id: uuid.UUID
    raised_by_user_id: uuid.UUID
    status: str
    reason: str
    resolution_details: Optional[str] = None
    admin_notes: Optional[str] = None
    evidence: List[EvidenceResponse] = []
    timeline_logs: List[DisputeTimelineResponse] = []
    created_at: datetime
    updated_at: datetime

    model_config = {
        "from_attributes": True
    }

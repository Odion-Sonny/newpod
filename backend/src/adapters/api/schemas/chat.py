import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel

class MessageResponse(BaseModel):
    id: uuid.UUID
    conversation_id: uuid.UUID
    sender_id: uuid.UUID
    content: str
    attachment_url: Optional[str] = None
    is_read: bool
    read_at: Optional[datetime] = None
    created_at: datetime

    model_config = {
        "from_attributes": True
    }

class ConversationResponse(BaseModel):
    id: uuid.UUID
    participant1_id: uuid.UUID
    participant2_id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = {
        "from_attributes": True
    }

from abc import ABC, abstractmethod
from typing import Optional, List
from src.adapters.db.models import Conversation, Message

class MessageRepositoryInterface(ABC):
    @abstractmethod
    async def create_conversation(self, conv: Conversation) -> Conversation:
        pass

    @abstractmethod
    async def get_conversation(self, participant1_id: str, participant2_id: str) -> Optional[Conversation]:
        pass

    @abstractmethod
    async def get_conversation_by_id(self, conv_id: str) -> Optional[Conversation]:
        pass

    @abstractmethod
    async def create_message(self, msg: Message) -> Message:
        pass

    @abstractmethod
    async def get_messages_by_conversation(self, conv_id: str, limit: int = 100) -> List[Message]:
        pass

    @abstractmethod
    async def mark_messages_as_read(self, conv_id: str, reader_id: str) -> int:
        pass

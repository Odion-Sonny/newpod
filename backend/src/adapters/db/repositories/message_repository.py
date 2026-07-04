import uuid
from typing import Optional, List
from sqlalchemy import or_, and_, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from src.domain.repositories.message_repository import MessageRepositoryInterface
from src.adapters.db.models import Conversation, Message
from datetime import datetime, timezone

class SQLAlchemyMessageRepository(MessageRepositoryInterface):
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_conversation(self, conv: Conversation) -> Conversation:
        self.db.add(conv)
        await self.db.flush()
        return conv

    async def get_conversation(self, participant1_id: str, participant2_id: str) -> Optional[Conversation]:
        p1 = uuid.UUID(participant1_id) if isinstance(participant1_id, str) else participant1_id
        p2 = uuid.UUID(participant2_id) if isinstance(participant2_id, str) else participant2_id
        
        stmt = select(Conversation).where(
            or_(
                and_(Conversation.participant1_id == p1, Conversation.participant2_id == p2),
                and_(Conversation.participant1_id == p2, Conversation.participant2_id == p1)
            )
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_conversation_by_id(self, conv_id: str) -> Optional[Conversation]:
        uid = uuid.UUID(conv_id) if isinstance(conv_id, str) else conv_id
        stmt = select(Conversation).where(Conversation.id == uid)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def create_message(self, msg: Message) -> Message:
        self.db.add(msg)
        stmt = (
            update(Conversation)
            .where(Conversation.id == msg.conversation_id)
            .values(updated_at=datetime.now(timezone.utc))
        )
        await self.db.execute(stmt)
        await self.db.flush()
        return msg

    async def get_messages_by_conversation(self, conv_id: str, limit: int = 100) -> List[Message]:
        uid = uuid.UUID(conv_id) if isinstance(conv_id, str) else conv_id
        stmt = (
            select(Message)
            .where(Message.conversation_id == uid)
            .order_by(Message.created_at.desc())
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        messages = list(result.scalars().all())
        messages.reverse()
        return messages

    async def mark_messages_as_read(self, conv_id: str, reader_id: str) -> int:
        uid = uuid.UUID(conv_id) if isinstance(conv_id, str) else conv_id
        ruid = uuid.UUID(reader_id) if isinstance(reader_id, str) else reader_id
        
        stmt = (
            update(Message)
            .where(
                Message.conversation_id == uid,
                Message.sender_id != ruid,
                Message.is_read.is_(False)
            )
            .values(is_read=True, read_at=datetime.now(timezone.utc))
        )
        result = await self.db.execute(stmt)
        await self.db.flush()
        return result.rowcount

import uuid
from typing import Optional, List, Dict, Tuple
from fastapi import WebSocket, HTTPException
from src.domain.repositories.message_repository import MessageRepositoryInterface
from src.domain.repositories.escrow_repository import EscrowRepositoryInterface
from src.adapters.db.models import Conversation, Message

class ConnectionManager:
    def __init__(self):
        # Maps escrow_id (str) -> list of tuple (user_id, WebSocket)
        self.active_connections: Dict[str, List[Tuple[str, WebSocket]]] = {}

    async def connect(self, escrow_id: str, user_id: str, websocket: WebSocket):
        await websocket.accept()
        if escrow_id not in self.active_connections:
            self.active_connections[escrow_id] = []
        self.active_connections[escrow_id].append((user_id, websocket))

    def disconnect(self, escrow_id: str, user_id: str, websocket: WebSocket):
        if escrow_id in self.active_connections:
            # Filter out this connection
            self.active_connections[escrow_id] = [
                conn for conn in self.active_connections[escrow_id] if conn[1] != websocket
            ]
            if not self.active_connections[escrow_id]:
                del self.active_connections[escrow_id]

    async def send_personal_message(self, message: dict, websocket: WebSocket):
        await websocket.send_json(message)

    async def broadcast_to_escrow(self, escrow_id: str, message: dict):
        if escrow_id in self.active_connections:
            for user_id, websocket in self.active_connections[escrow_id]:
                try:
                    await websocket.send_json(message)
                except Exception:
                    # Connection might be dead, clean up happens on disconnect
                    pass

manager = ConnectionManager()

class ChatService:
    def __init__(self, message_repo: MessageRepositoryInterface, escrow_repo: EscrowRepositoryInterface):
        self.message_repo = message_repo
        self.escrow_repo = escrow_repo

    async def get_or_create_conversation(self, participant1_id: str, participant2_id: str) -> Conversation:
        conv = await self.message_repo.get_conversation(participant1_id, participant2_id)
        if not conv:
            p1 = uuid.UUID(participant1_id) if isinstance(participant1_id, str) else participant1_id
            p2 = uuid.UUID(participant2_id) if isinstance(participant2_id, str) else participant2_id
            new_conv = Conversation(participant1_id=p1, participant2_id=p2)
            conv = await self.message_repo.create_conversation(new_conv)
        return conv

    async def save_message(
        self,
        conversation_id: str,
        sender_id: str,
        content: str,
        attachment_url: Optional[str] = None
    ) -> Message:
        conv_uuid = uuid.UUID(conversation_id) if isinstance(conversation_id, str) else conversation_id
        sender_uuid = uuid.UUID(sender_id) if isinstance(sender_id, str) else sender_id
        
        msg = Message(
            conversation_id=conv_uuid,
            sender_id=sender_uuid,
            content=content,
            attachment_url=attachment_url,
            is_read=False
        )
        return await self.message_repo.create_message(msg)

    async def get_messages(self, conversation_id: str, limit: int = 100) -> List[Message]:
        return await self.message_repo.get_messages_by_conversation(conversation_id, limit=limit)

    async def mark_as_read(self, conversation_id: str, reader_id: str) -> int:
        return await self.message_repo.mark_messages_as_read(conversation_id, reader_id)

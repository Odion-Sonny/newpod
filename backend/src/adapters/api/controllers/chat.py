from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
import uuid
import json
from typing import List

from src.core.database import get_db
from src.adapters.api.dependencies import get_current_user
from src.adapters.db.models import User
from src.core.security import decode_token
from src.adapters.db.repositories.user_repository import SQLAlchemyUserRepository
from src.adapters.db.repositories.escrow_repository import SQLAlchemyEscrowRepository
from src.adapters.db.repositories.message_repository import SQLAlchemyMessageRepository
from src.use_cases.chat import ChatService, manager
from src.adapters.api.schemas.chat import MessageResponse

router = APIRouter(tags=["Chat"])

def get_chat_service(db: AsyncSession = Depends(get_db)) -> ChatService:
    message_repo = SQLAlchemyMessageRepository(db)
    escrow_repo = SQLAlchemyEscrowRepository(db)
    return ChatService(message_repo, escrow_repo)

@router.get("/escrows/{escrow_id}/chat/messages", response_model=List[MessageResponse])
async def get_chat_messages(
    escrow_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    service: ChatService = Depends(get_chat_service)
):
    escrow_repo = SQLAlchemyEscrowRepository(db)
    escrow = await escrow_repo.get_escrow_by_id(str(escrow_id))
    if not escrow:
        raise HTTPException(status_code=404, detail="Escrow not found")

    user_roles = [role.name for role in current_user.roles]
    if "ADMIN" not in user_roles and current_user.id not in [escrow.buyer_id, escrow.seller_id]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not authorized to view this escrow's chat"
        )

    # Get conversation
    conv = await service.get_or_create_conversation(str(escrow.buyer_id), str(escrow.seller_id))
    
    # Mark messages as read for the reader
    await service.mark_as_read(str(conv.id), str(current_user.id))
    
    return await service.get_messages(str(conv.id))

@router.websocket("/escrows/{escrow_id}/chat/ws")
async def websocket_chat_endpoint(
    websocket: WebSocket,
    escrow_id: uuid.UUID,
    token: str = Query(...),
    db: AsyncSession = Depends(get_db)
):
    # 1. Authenticate WS connection
    try:
        payload = decode_token(token)
        if not payload or payload.get("type") != "access":
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return
        user_id = payload.get("sub")
        user_repo = SQLAlchemyUserRepository(db)
        user = await user_repo.get_by_id(user_id)
        if not user:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return
    except Exception:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    # 2. Verify authorization
    escrow_repo = SQLAlchemyEscrowRepository(db)
    escrow = await escrow_repo.get_escrow_by_id(str(escrow_id))
    if not escrow:
        await websocket.close(code=status.WS_1011_INTERNAL_ERROR)
        return

    user_roles = [role.name for role in user.roles]
    if "ADMIN" not in user_roles and user.id not in [escrow.buyer_id, escrow.seller_id]:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    chat_service = ChatService(SQLAlchemyMessageRepository(db), escrow_repo)
    conv = await chat_service.get_or_create_conversation(str(escrow.buyer_id), str(escrow.seller_id))

    # 3. Add to ConnectionManager
    await manager.connect(str(escrow_id), str(user.id), websocket)
    
    # Send system update or read receipt broadcast on join
    await chat_service.mark_as_read(str(conv.id), str(user.id))
    await db.commit()
    await manager.broadcast_to_escrow(str(escrow_id), {
        "type": "read_receipt",
        "reader_id": str(user.id),
        "conversation_id": str(conv.id)
    })

    try:
        while True:
            # Receive text
            data = await websocket.receive_text()
            try:
                event = json.loads(data)
            except Exception:
                continue

            event_type = event.get("type", "message")

            if event_type == "message":
                content = event.get("content")
                attachment_url = event.get("attachment_url")
                if not content:
                    continue

                # Save to db
                msg = await chat_service.save_message(
                    conversation_id=str(conv.id),
                    sender_id=str(user.id),
                    content=content,
                    attachment_url=attachment_url
                )
                await db.commit()
                # Broadcast
                await manager.broadcast_to_escrow(str(escrow_id), {
                    "type": "message",
                    "id": str(msg.id),
                    "conversation_id": str(conv.id),
                    "sender_id": str(user.id),
                    "content": msg.content,
                    "attachment_url": msg.attachment_url,
                    "created_at": msg.created_at.isoformat()
                })

            elif event_type == "read":
                # Mark as read and notify
                await chat_service.mark_as_read(str(conv.id), str(user.id))
                await db.commit()
                await manager.broadcast_to_escrow(str(escrow_id), {
                    "type": "read_receipt",
                    "reader_id": str(user.id),
                    "conversation_id": str(conv.id)
                })

    except WebSocketDisconnect:
        manager.disconnect(str(escrow_id), str(user.id), websocket)

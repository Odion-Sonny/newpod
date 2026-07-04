from fastapi import APIRouter, Depends, HTTPException, status, File, UploadFile, Form
from sqlalchemy.ext.asyncio import AsyncSession
import uuid
from typing import List

from src.core.database import get_db
from src.adapters.api.dependencies import get_current_user, check_role
from src.adapters.db.models import User, EvidenceType
from src.adapters.db.repositories.dispute_repository import SQLAlchemyDisputeRepository
from src.adapters.db.repositories.escrow_repository import SQLAlchemyEscrowRepository
from src.adapters.db.repositories.ledger_repository import SQLAlchemyLedgerRepository
from src.use_cases.dispute import DisputeService
from src.use_cases.ledger import LedgerService
from src.adapters.api.schemas.dispute import (
    DisputeRaiseRequest, DisputeResolveRequest, DisputeResponse, EvidenceResponse
)

router = APIRouter(prefix="/disputes", tags=["Disputes"])

def get_dispute_service(db: AsyncSession = Depends(get_db)) -> DisputeService:
    dispute_repo = SQLAlchemyDisputeRepository(db)
    escrow_repo = SQLAlchemyEscrowRepository(db)
    ledger_repo = SQLAlchemyLedgerRepository(db)
    ledger_service = LedgerService(ledger_repo)
    return DisputeService(dispute_repo, escrow_repo, ledger_service)

@router.post("", response_model=DisputeResponse, status_code=status.HTTP_201_CREATED)
async def raise_dispute(
    data: DisputeRaiseRequest,
    current_user: User = Depends(get_current_user),
    service: DisputeService = Depends(get_dispute_service)
):
    return await service.raise_dispute(
        escrow_id=str(data.escrow_id),
        buyer_id=str(current_user.id),
        reason=data.reason
    )

@router.post("/{dispute_id}/evidence", response_model=EvidenceResponse, status_code=status.HTTP_201_CREATED)
async def upload_evidence(
    dispute_id: uuid.UUID,
    file: UploadFile = File(...),
    file_type: EvidenceType = Form(...),
    current_user: User = Depends(get_current_user),
    service: DisputeService = Depends(get_dispute_service)
):
    content = await file.read()
    return await service.upload_evidence(
        dispute_id=str(dispute_id),
        user_id=str(current_user.id),
        file_content=content,
        filename=file.filename or "evidence",
        file_type=file_type
    )

@router.post("/{dispute_id}/resolve", response_model=DisputeResponse)
async def resolve_dispute(
    dispute_id: uuid.UUID,
    data: DisputeResolveRequest,
    current_user: User = Depends(check_role("ADMIN")),
    service: DisputeService = Depends(get_dispute_service)
):
    return await service.resolve_dispute(
        dispute_id=str(dispute_id),
        admin_id=str(current_user.id),
        verdict=data.verdict,
        resolution_details=data.resolution_details
    )

@router.get("/{dispute_id}", response_model=DisputeResponse)
async def get_dispute(
    dispute_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    service: DisputeService = Depends(get_dispute_service)
):
    # Verify participant/admin permission
    dispute = await service.get_dispute(str(dispute_id))
    user_roles = [role.name for role in current_user.roles]
    if "ADMIN" not in user_roles and current_user.id not in [dispute.escrow.buyer_id, dispute.escrow.seller_id]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not authorized to view this dispute"
        )
    return dispute

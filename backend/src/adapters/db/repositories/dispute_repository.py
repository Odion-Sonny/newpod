import uuid
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from src.domain.repositories.dispute_repository import DisputeRepositoryInterface
from src.adapters.db.models import Dispute, Evidence, DisputeTimeline, Escrow

class SQLAlchemyDisputeRepository(DisputeRepositoryInterface):
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_dispute(self, dispute: Dispute) -> Dispute:
        self.db.add(dispute)
        await self.db.flush()
        return dispute

    async def get_dispute_by_id(self, dispute_id: str) -> Optional[Dispute]:
        uid = uuid.UUID(dispute_id) if isinstance(dispute_id, str) else dispute_id
        stmt = (
            select(Dispute)
            .where(Dispute.id == uid)
            .options(
                selectinload(Dispute.evidence),
                selectinload(Dispute.timeline_logs),
                selectinload(Dispute.escrow).selectinload(Escrow.order)
            )
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_dispute_by_escrow_id(self, escrow_id: str) -> Optional[Dispute]:
        uid = uuid.UUID(escrow_id) if isinstance(escrow_id, str) else escrow_id
        stmt = (
            select(Dispute)
            .where(Dispute.escrow_id == uid)
            .options(
                selectinload(Dispute.evidence),
                selectinload(Dispute.timeline_logs),
                selectinload(Dispute.escrow).selectinload(Escrow.order)
            )
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def update_dispute(self, dispute: Dispute) -> Dispute:
        self.db.add(dispute)
        await self.db.flush()
        return dispute

    async def create_evidence(self, evidence: Evidence) -> Evidence:
        self.db.add(evidence)
        await self.db.flush()
        return evidence

    async def create_timeline_log(self, log: DisputeTimeline) -> DisputeTimeline:
        self.db.add(log)
        await self.db.flush()
        return log

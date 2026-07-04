from abc import ABC, abstractmethod
from typing import Optional, List
from src.adapters.db.models import Dispute, Evidence, DisputeTimeline

class DisputeRepositoryInterface(ABC):
    @abstractmethod
    async def create_dispute(self, dispute: Dispute) -> Dispute:
        pass

    @abstractmethod
    async def get_dispute_by_id(self, dispute_id: str) -> Optional[Dispute]:
        pass

    @abstractmethod
    async def get_dispute_by_escrow_id(self, escrow_id: str) -> Optional[Dispute]:
        pass

    @abstractmethod
    async def update_dispute(self, dispute: Dispute) -> Dispute:
        pass

    @abstractmethod
    async def create_evidence(self, evidence: Evidence) -> Evidence:
        pass

    @abstractmethod
    async def create_timeline_log(self, log: DisputeTimeline) -> DisputeTimeline:
        pass

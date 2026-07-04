import os
import uuid
import hashlib
from typing import Optional, List
from fastapi import HTTPException, status
from src.domain.repositories.dispute_repository import DisputeRepositoryInterface
from src.domain.repositories.escrow_repository import EscrowRepositoryInterface
from src.use_cases.ledger import LedgerService
from src.adapters.db.models import Dispute, Evidence, DisputeTimeline, EscrowStatus, DisputeStatus, EvidenceType

class DisputeService:
    def __init__(
        self,
        dispute_repo: DisputeRepositoryInterface,
        escrow_repo: EscrowRepositoryInterface,
        ledger_service: LedgerService
    ):
        self.dispute_repo = dispute_repo
        self.escrow_repo = escrow_repo
        self.ledger_service = ledger_service
        # Create upload directory
        os.makedirs("uploads", exist_ok=True)

    async def raise_dispute(self, escrow_id: str, buyer_id: str, reason: str) -> Dispute:
        escrow = await self.escrow_repo.get_escrow_by_id(escrow_id)
        if not escrow:
            raise HTTPException(status_code=404, detail="Escrow not found")

        buyer_uuid = uuid.UUID(buyer_id) if isinstance(buyer_id, str) else buyer_id
        if escrow.buyer_id != buyer_uuid:
            raise HTTPException(status_code=403, detail="Only the buyer can raise a dispute")

        # Can only dispute once items are shipped, delivered, or in inspection window
        if escrow.status not in [EscrowStatus.SHIPPED, EscrowStatus.DELIVERED, EscrowStatus.INSPECTION_WINDOW]:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot open dispute in status: {escrow.status.value}"
            )

        # Transition escrow states
        escrow.status = EscrowStatus.DISPUTED
        escrow.order.status = "disputed"
        await self.escrow_repo.update_escrow(escrow)

        # Create dispute record
        dispute = Dispute(
            escrow_id=escrow.id,
            raised_by_user_id=buyer_uuid,
            status=DisputeStatus.OPEN,
            reason=reason
        )
        dispute.evidence = []
        dispute.timeline_logs = []
        created_dispute = await self.dispute_repo.create_dispute(dispute)

        # Create timeline log
        log = DisputeTimeline(
            dispute_id=created_dispute.id,
            event_type="DISPUTE_OPENED",
            description=f"Dispute raised by buyer: {reason}",
            metadata_json={"user_id": str(buyer_id)}
        )
        await self.dispute_repo.create_timeline_log(log)
        created_dispute.timeline_logs.append(log)

        return created_dispute

    async def upload_evidence(
        self,
        dispute_id: str,
        user_id: str,
        file_content: bytes,
        filename: str,
        file_type: EvidenceType
    ) -> Evidence:
        dispute = await self.dispute_repo.get_dispute_by_id(dispute_id)
        if not dispute:
            raise HTTPException(status_code=404, detail="Dispute not found")

        user_uuid = uuid.UUID(user_id) if isinstance(user_id, str) else user_id
        escrow = dispute.escrow
        if user_uuid not in [escrow.buyer_id, escrow.seller_id]:
            raise HTTPException(status_code=403, detail="Only participants of this escrow can upload evidence")

        # Calculate file hash for integrity checks
        sha256 = hashlib.sha256(file_content).hexdigest()

        # Save file locally
        ext = filename.split(".")[-1] if "." in filename else ""
        unique_name = f"{uuid.uuid4()}.{ext}" if ext else f"{uuid.uuid4()}"
        file_path = os.path.join("uploads", unique_name)
        with open(file_path, "wb") as f:
            f.write(file_content)

        file_url = f"/uploads/{unique_name}"

        # Save evidence record
        evidence = Evidence(
            dispute_id=dispute.id,
            uploaded_by_user_id=user_uuid,
            file_url=file_url,
            file_type=file_type,
            hash=sha256
        )
        created_evidence = await self.dispute_repo.create_evidence(evidence)
        dispute.evidence.append(created_evidence)

        # Create timeline log
        log = DisputeTimeline(
            dispute_id=dispute.id,
            event_type="EVIDENCE_SUBMITTED",
            description=f"Evidence submitted by {'Buyer' if user_uuid == escrow.buyer_id else 'Seller'}",
            metadata_json={"user_id": str(user_id), "file_url": file_url, "hash": sha256}
        )
        await self.dispute_repo.create_timeline_log(log)
        dispute.timeline_logs.append(log)

        return created_evidence

    async def resolve_dispute(
        self,
        dispute_id: str,
        admin_id: str,
        verdict: str,
        resolution_details: str
    ) -> Dispute:
        dispute = await self.dispute_repo.get_dispute_by_id(dispute_id)
        if not dispute:
            raise HTTPException(status_code=404, detail="Dispute not found")

        if dispute.status == DisputeStatus.RESOLVED:
            raise HTTPException(status_code=400, detail="Dispute is already resolved")

        escrow = dispute.escrow
        if escrow.status != EscrowStatus.DISPUTED:
            raise HTTPException(status_code=400, detail="Associated escrow is not in DISPUTED status")

        if verdict == "REFUND_BUYER":
            escrow.status = EscrowStatus.REFUNDED
            escrow.order.status = "refunded"
            await self.ledger_service.refund_escrow_payment(escrow)
        elif verdict == "PAY_SELLER":
            escrow.status = EscrowStatus.RELEASED
            escrow.order.status = "completed"
            await self.ledger_service.release_escrow_payout(escrow)
        else:
            raise HTTPException(status_code=400, detail="Invalid verdict")

        # Update escrow state
        await self.escrow_repo.update_escrow(escrow)

        # Update dispute
        dispute.status = DisputeStatus.RESOLVED
        dispute.resolution_details = resolution_details
        dispute.admin_notes = f"Resolved by admin {admin_id} with verdict: {verdict}"
        await self.dispute_repo.update_dispute(dispute)

        # Log timeline
        log = DisputeTimeline(
            dispute_id=dispute.id,
            event_type="DISPUTE_RESOLVED",
            description=f"Dispute resolved in favor of {'Buyer' if verdict == 'REFUND_BUYER' else 'Seller'}",
            metadata_json={"admin_id": str(admin_id), "verdict": verdict, "details": resolution_details}
        )
        await self.dispute_repo.create_timeline_log(log)
        dispute.timeline_logs.append(log)

        return dispute

    async def get_dispute(self, dispute_id: str) -> Dispute:
        dispute = await self.dispute_repo.get_dispute_by_id(dispute_id)
        if not dispute:
            raise HTTPException(status_code=404, detail="Dispute not found")
        return dispute

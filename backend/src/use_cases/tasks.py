import asyncio
from datetime import datetime, timezone, timedelta
from sqlalchemy import select
from celery.utils.log import get_task_logger

from src.core.celery_app import celery_app
from src.core.database import AsyncSessionLocal
from src.adapters.db.repositories.escrow_repository import SQLAlchemyEscrowRepository
from src.use_cases.escrow import EscrowService
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from src.adapters.db.models import Escrow, EscrowStatus

logger = get_task_logger(__name__)

async def _run_auto_release(hours: int, db: AsyncSession):
    escrow_repo = SQLAlchemyEscrowRepository(db)
    escrow_service = EscrowService(escrow_repo)
    
    # Select all escrows in INSPECTION_WINDOW status
    # that were last updated before (now - threshold)
    threshold = datetime.now(timezone.utc) - timedelta(hours=hours)
    stmt = (
        select(Escrow)
        .where(
            Escrow.status == EscrowStatus.INSPECTION_WINDOW,
            Escrow.updated_at < threshold
        )
        .options(selectinload(Escrow.order))
    )
    result = await db.execute(stmt)
    expired_escrows = result.scalars().all()
    
    if not expired_escrows:
        logger.info("No expired escrows in inspection window found.")
        return

    logger.info(f"Found {len(expired_escrows)} expired escrows. Auto-releasing...")
    for escrow in expired_escrows:
        try:
            # Release the escrow bypassing buyer checks
            await escrow_service.release_escrow(
                escrow_id=str(escrow.id),
                user_id=str(escrow.buyer_id),
                is_admin=True
            )
            logger.info(f"Escrow {escrow.id} auto-released successfully.")
        except Exception as e:
            logger.error(f"Failed to auto-release escrow {escrow.id}: {str(e)}")

async def auto_release_expired_escrows_async(hours: int = 24, db: AsyncSession = None):
    if db is not None:
        await _run_auto_release(hours, db)
    else:
        async with AsyncSessionLocal() as session:
            await _run_auto_release(hours, session)
            await session.commit()

@celery_app.task(name="src.use_cases.tasks.auto_release_expired_escrows")
def auto_release_expired_escrows(hours: int = 24):
    """
    Background task to scan and auto-release escrows in inspection window
    whose window has expired.
    """
    logger.info("Running auto_release_expired_escrows background task...")
    asyncio.run(auto_release_expired_escrows_async(hours))

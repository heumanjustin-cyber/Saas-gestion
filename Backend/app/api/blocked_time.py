from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.dependencies import get_db

from app.models.blocked_time import BlockedTime

from app.schemas.blocked_time import (
    BlockedTimeCreate,
)

router = APIRouter()


@router.post("/blocked-times")
def create_blocked_time(
    blocked_time: BlockedTimeCreate,
    db: Session = Depends(get_db)
):
    new_block = BlockedTime(
        employee_id=UUID(
            blocked_time.employee_id
        ),
        starts_at=datetime.fromisoformat(
            blocked_time.starts_at
        ),
        ends_at=datetime.fromisoformat(
            blocked_time.ends_at
        ),
        reason=blocked_time.reason,
    )

    db.add(new_block)
    db.commit()
    db.refresh(new_block)

    return {
        "id": str(new_block.id)
    }


@router.get("/blocked-times")
def get_blocked_times(
    db: Session = Depends(get_db)
):
    return db.query(
        BlockedTime
    ).all()
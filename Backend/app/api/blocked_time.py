from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.core.tenancy import get_mine_or_404, my_company_ids
from app.db.dependencies import get_db
from app.models.blocked_time import BlockedTime
from app.models.employee import Employee
from app.schemas.blocked_time import BlockedTimeCreate

router = APIRouter()


@router.post("/blocked-times")
def create_blocked_time(
    blocked_time: BlockedTimeCreate,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    get_mine_or_404(db, Employee, blocked_time.employee_id, current_user, "Empleado")
    new_block = BlockedTime(
        employee_id=blocked_time.employee_id,
        starts_at=blocked_time.starts_at,
        ends_at=blocked_time.ends_at,
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
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return db.query(BlockedTime).join(Employee, Employee.id == BlockedTime.employee_id).filter(
        Employee.company_id.in_(my_company_ids(db, current_user))
    ).all()

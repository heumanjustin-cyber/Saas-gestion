from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.core.tenancy import get_mine_or_404, my_company_ids
from app.db.dependencies import get_db
from app.models.employee import Employee
from app.models.employee_schedule import EmployeeSchedule
from app.schemas.employee_schedule import EmployeeScheduleCreate

router = APIRouter()


@router.post("/employee-schedules")
def create_employee_schedule(
    schedule: EmployeeScheduleCreate,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    get_mine_or_404(db, Employee, schedule.employee_id, current_user, "Empleado")
    new_schedule = EmployeeSchedule(
        employee_id=schedule.employee_id,
        weekday=schedule.weekday,
        start_time=schedule.start_time,
        end_time=schedule.end_time,
    )

    db.add(new_schedule)
    db.commit()
    db.refresh(new_schedule)

    return {
        "id": str(new_schedule.id)
    }


@router.get("/employee-schedules")
def get_employee_schedules(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return db.query(EmployeeSchedule).join(Employee, Employee.id == EmployeeSchedule.employee_id).filter(
        Employee.company_id.in_(my_company_ids(db, current_user))
    ).all()

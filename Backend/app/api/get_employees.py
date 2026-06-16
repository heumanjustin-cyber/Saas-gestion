from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.dependencies import get_db
from app.models.employee import Employee

router = APIRouter()


@router.get("/employees")
def get_employees(
    db: Session = Depends(get_db)
):
    employees = db.query(Employee).all()

    return employees
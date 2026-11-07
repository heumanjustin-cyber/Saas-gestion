from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.core.tenancy import my_company_ids
from app.db.dependencies import get_db
from app.models.company import Company

router = APIRouter()


def list_my_companies(db: Session, user) -> list[Company]:
    """Solo las empresas del usuario (antes devolvía las de todos los clientes del SaaS)."""
    return db.query(Company).filter(Company.id.in_(my_company_ids(db, user))).all()


@router.get("/companies")
def get_companies(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return list_my_companies(db, current_user)

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.core.tenancy import my_company_ids
from app.db.dependencies import get_db
from app.models.membership import CompanyMembership
from app.models.permission import Permission
from app.models.role import Role

router = APIRouter(
    prefix="/access",
    tags=["access"]
)


@router.get("/permissions")
def get_permissions(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Catálogo de permisos: es el mismo para todos, pero solo para usuarios con sesión
    return db.query(Permission).all()


@router.get("/roles")
def get_roles(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return db.query(Role).filter(Role.company_id.in_(my_company_ids(db, current_user))).all()


@router.get("/memberships")
def get_memberships(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return db.query(CompanyMembership).filter(
        CompanyMembership.company_id.in_(my_company_ids(db, current_user))
    ).all()

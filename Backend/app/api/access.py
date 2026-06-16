from fastapi import APIRouter
from sqlalchemy.orm import Session
from fastapi import Depends

from app.db.dependencies import get_db

from app.models.permission import Permission
from app.models.role import Role
from app.models.membership import CompanyMembership

router = APIRouter(
    prefix="/access",
    tags=["access"]
)


@router.get("/permissions")
def get_permissions(
    db: Session = Depends(get_db)
):
    return db.query(
        Permission
    ).all()


@router.get("/roles")
def get_roles(
    db: Session = Depends(get_db)
):
    return db.query(
        Role
    ).all()


@router.get("/memberships")
def get_memberships(
    db: Session = Depends(get_db)
):
    return db.query(
        CompanyMembership
    ).all()
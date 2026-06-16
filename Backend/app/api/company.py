from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.db.dependencies import get_db

from app.models.company import Company

from app.schemas.company import CompanyCreate

from app.services.access_service import (
    create_default_roles,
    create_owner_membership,
)

router = APIRouter()


@router.post("/companies")
def create_company(
    company: CompanyCreate,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    existing_company = db.query(
        Company
    ).filter(
        Company.slug == company.slug
    ).first()

    if existing_company:
        return {
            "error": "Slug already exists"
        }

    new_company = Company(
        name=company.name,
        slug=company.slug,
        owner_user_id=current_user.id
    )

    db.add(new_company)

    db.commit()
    db.refresh(new_company)

    create_default_roles(
        db=db,
        company=new_company
    )

    create_owner_membership(
        db=db,
        company=new_company,
        user=current_user
    )

    return {
        "id": str(new_company.id),
        "name": new_company.name,
        "slug": new_company.slug,
        "owner_user_id": str(
            new_company.owner_user_id
        )
    }


@router.get("/companies")
def get_companies(
    db: Session = Depends(get_db)
):
    return db.query(
        Company
    ).all()
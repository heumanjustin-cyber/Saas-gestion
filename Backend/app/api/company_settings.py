from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.db.dependencies import get_db

from app.models.company import Company
from app.models.company_settings import CompanySettings

from app.schemas.company_settings import (
    CompanySettingsCreate
)

router = APIRouter()


@router.post("/company-settings")
def create_company_settings(
    settings: CompanySettingsCreate,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    company = db.query(Company).filter(
        Company.id == UUID(settings.company_id)
    ).first()

    if not company:
        raise HTTPException(
            status_code=404,
            detail="Company not found"
        )

    if company.owner_user_id != current_user.id:
        raise HTTPException(
            status_code=403,
            detail="You do not own this company"
        )

    existing = db.query(
        CompanySettings
    ).filter(
        CompanySettings.company_id == UUID(
            settings.company_id
        )
    ).first()

    if existing:
        raise HTTPException(
            status_code=400,
            detail="Settings already exist"
        )

    new_settings = CompanySettings(
        company_id=UUID(settings.company_id),
        business_type=settings.business_type,
        whatsapp_number=settings.whatsapp_number,
        instagram_username=settings.instagram_username,
        website=settings.website,
    )

    db.add(new_settings)
    db.commit()
    db.refresh(new_settings)

    return new_settings
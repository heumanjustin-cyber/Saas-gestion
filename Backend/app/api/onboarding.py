from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.db.dependencies import get_db

from app.models.company import Company
from app.models.company_settings import CompanySettings

from app.schemas.onboarding import (
    OnboardingRequest
)

router = APIRouter()


@router.post("/onboarding")
def onboarding(
    data: OnboardingRequest,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    company = db.query(Company).filter(
        Company.id == UUID(data.company_id)
    ).first()

    if not company:
        raise HTTPException(
            status_code=404,
            detail="Company not found"
        )

    if company.owner_user_id != current_user.id:
        raise HTTPException(
            status_code=403,
            detail="Not allowed"
        )

    settings = db.query(
        CompanySettings
    ).filter(
        CompanySettings.company_id == company.id
    ).first()

    if not settings:
        settings = CompanySettings(
            company_id=company.id
        )
        db.add(settings)

    settings.business_type = data.business_type
    settings.whatsapp_number = data.whatsapp_number
    settings.instagram_username = data.instagram_username
    settings.website = data.website
    settings.ai_enabled = data.enable_ai
    settings.automatic_reminders = (
        data.enable_reminders
    )

    db.commit()
    db.refresh(settings)

    return {
        "success": True,
        "company_id": str(company.id),
        "business_type": settings.business_type,
        "ai_enabled": settings.ai_enabled,
        "automatic_reminders":
            settings.automatic_reminders
    }
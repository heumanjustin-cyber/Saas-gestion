from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.db.dependencies import get_db

from app.models.company import Company
from app.models.company_settings import CompanySettings

router = APIRouter()


@router.get("/my-setup-status")
def get_setup_status(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    company_ids = [
        company.id
        for company in db.query(Company).filter(
            Company.owner_user_id == current_user.id
        ).all()
    ]

    settings = db.query(
        CompanySettings
    ).filter(
        CompanySettings.company_id.in_(company_ids)
    ).first()

    if not settings:
        return {
            "configured": False
        }

    score = 0

    if settings.whatsapp_number:
        score += 25

    if settings.instagram_username:
        score += 25

    if settings.website:
        score += 25

    if settings.online_booking_enabled:
        score += 25

    return {
        "configured": True,
        "business_type": settings.business_type,
        "setup_score": score,
        "ai_enabled": settings.ai_enabled,
        "online_booking_enabled": settings.online_booking_enabled,
        "whatsapp_configured": bool(settings.whatsapp_number),
        "instagram_configured": bool(settings.instagram_username),
        "website_configured": bool(settings.website)
    }
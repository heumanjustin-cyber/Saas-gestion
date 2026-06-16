from pydantic import BaseModel


class OnboardingRequest(BaseModel):
    company_id: str
    business_type: str

    whatsapp_number: str | None = None
    instagram_username: str | None = None
    website: str | None = None

    enable_ai: bool = False
    enable_reminders: bool = False
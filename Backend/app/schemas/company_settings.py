from pydantic import BaseModel


class CompanySettingsCreate(BaseModel):
    company_id: str
    business_type: str
    whatsapp_number: str | None = None
    instagram_username: str | None = None
    website: str | None = None
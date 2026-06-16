from pydantic import BaseModel


class ResourceCreate(BaseModel):
    company_id: str
    location_id: str | None = None
    name: str
    resource_type: str
    description: str | None = None
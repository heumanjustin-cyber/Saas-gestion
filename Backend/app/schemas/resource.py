from uuid import UUID
from pydantic import BaseModel

class ResourceCreate(BaseModel):
    company_id: UUID
    location_id: UUID | None = None
    name: str
    resource_type: str
    description: str | None = None

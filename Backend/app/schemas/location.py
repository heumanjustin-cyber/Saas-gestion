from pydantic import BaseModel


class LocationCreate(BaseModel):
    company_id: str
    name: str
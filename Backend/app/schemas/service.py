from pydantic import BaseModel


class ServiceCreate(BaseModel):
    company_id: str
    name: str
    duration_minutes: int
    price: float
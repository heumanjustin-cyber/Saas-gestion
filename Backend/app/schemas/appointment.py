from pydantic import BaseModel


class AppointmentCreate(BaseModel):
    company_id: str
    client_id: str
    employee_id: str
    service_id: str
    starts_at: str
    ends_at: str
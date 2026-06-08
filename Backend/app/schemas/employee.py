from pydantic import BaseModel


class EmployeeCreate(BaseModel):
    company_id: str
    first_name: str
    last_name: str
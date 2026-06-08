from pydantic import BaseModel


class ClientCreate(BaseModel):
    company_id: str
    first_name: str
    last_name: str
    phone: str
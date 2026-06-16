from pydantic import BaseModel


class CompanyCreateRequest(BaseModel):
    name: str
    slug: str
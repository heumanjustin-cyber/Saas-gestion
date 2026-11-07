import re

from pydantic import BaseModel, field_validator

SLUG = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


class CompanyCreate(BaseModel):
    name: str
    slug: str

    @field_validator("name")
    @classmethod
    def _name(cls, v: str) -> str:
        v = v.strip()
        if not 2 <= len(v) <= 150:
            raise ValueError("El nombre debe tener entre 2 y 150 caracteres")
        return v

    @field_validator("slug")
    @classmethod
    def _slug(cls, v: str) -> str:
        # Va en las direcciones públicas (/r/<slug>): minúsculas, números y guiones
        v = v.strip().lower()
        if not 3 <= len(v) <= 60 or not SLUG.match(v):
            raise ValueError("El slug solo puede llevar minúsculas, números y guiones (3 a 60 caracteres)")
        return v

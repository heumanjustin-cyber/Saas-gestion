from pydantic import BaseModel


class RegisterRequest(BaseModel):
    email: str
    password: str
    full_name: str
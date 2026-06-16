from pydantic import BaseModel


class UserResponse(BaseModel):
    id: str
    email: str
    full_name: str
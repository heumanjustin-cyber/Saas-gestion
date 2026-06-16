from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.dependencies import get_db
from app.models.user import User

from app.schemas.auth import LoginRequest
from app.core.security import verify_password
from app.core.jwt import create_access_token

router = APIRouter()


@router.post("/login")
def login(
    credentials: LoginRequest,
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(
        User.email == credentials.email
    ).first()

    if not user:
        return {
            "error": "Email o contraseña incorrectos"
        }

    if not verify_password(
        credentials.password,
        user.hashed_password
    ):
        return {
            "error": "Email o contraseña incorrectos"
        }

    token = create_access_token(
        str(user.id)
    )

    return {
        "access_token": token,
        "token_type": "bearer"
    }
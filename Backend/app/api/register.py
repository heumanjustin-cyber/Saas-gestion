from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.jwt import create_access_token
from app.core.security import hash_password
from app.db.dependencies import get_db
from app.models.user import User
from app.schemas.register import RegisterRequest
from app.services import ratelimit

router = APIRouter()


@router.post("/register")
def register(
    user: RegisterRequest,
    request: Request,
    db: Session = Depends(get_db)
):
    ratelimit.check("register", ratelimit.client_key(request), limit=10, window_seconds=3600)
    existing_user = db.query(User).filter(func.lower(User.email) == user.email.lower()).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Email ya registrado")

    new_user = User(
        email=user.email,
        hashed_password=hash_password(user.password),
        full_name=user.full_name,
        is_active=True,
        is_verified=True,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return {
        "id": str(new_user.id),
        "email": new_user.email,
        "full_name": new_user.full_name,
        "access_token": create_access_token(str(new_user.id)),
        "token_type": "bearer",
    }

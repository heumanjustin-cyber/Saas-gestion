from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from jose import jwt
from datetime import datetime, timedelta
from app.db.dependencies import get_db
from app.models.user import User
from app.schemas.register import RegisterRequest
from app.core.security import hash_password
from app.core.config import SECRET_KEY, ALGORITHM

router = APIRouter()

@router.post("/register")
def register(
    user: RegisterRequest,
    db: Session = Depends(get_db)
):
    existing_user = db.query(User).filter(User.email == user.email).first()
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

    expire = datetime.utcnow() + timedelta(hours=24)
    token = jwt.encode({"sub": str(new_user.id), "exp": expire}, SECRET_KEY, algorithm=ALGORITHM)

    return {
        "id": str(new_user.id),
        "email": new_user.email,
        "full_name": new_user.full_name,
        "access_token": token,
        "token_type": "bearer",
    }

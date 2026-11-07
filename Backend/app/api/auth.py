from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.jwt import create_access_token
from app.core.security import DUMMY_HASH, hash_password, needs_rehash, verify_password
from app.db.dependencies import get_db
from app.models.user import User
from app.schemas.auth import LoginRequest
from app.services import ratelimit

router = APIRouter()

BAD_LOGIN = "Email o contraseña incorrectos"


@router.post("/login")
def login(
    credentials: LoginRequest,
    request: Request,
    db: Session = Depends(get_db)
):
    email = credentials.email.strip()
    # 10 intentos cada 15 minutos por IP y email: frena a quien prueba contraseñas
    ratelimit.check("login", f"{ratelimit.client_key(request)}:{email.lower()}", limit=10, window_seconds=900)

    user = db.query(User).filter(func.lower(User.email) == email.lower()).first()

    if not user:
        verify_password(credentials.password, DUMMY_HASH)  # mismo tiempo exista o no el email
        return JSONResponse(status_code=401, content={"error": BAD_LOGIN, "detail": BAD_LOGIN})

    if not verify_password(credentials.password, user.hashed_password):
        return JSONResponse(status_code=401, content={"error": BAD_LOGIN, "detail": BAD_LOGIN})

    if not user.is_active:
        return JSONResponse(status_code=403, content={"error": "Cuenta desactivada", "detail": "Cuenta desactivada"})

    if needs_rehash(user.hashed_password):
        user.hashed_password = hash_password(credentials.password)
        db.commit()

    token = create_access_token(
        str(user.id)
    )

    return {
        "access_token": token,
        "token_type": "bearer"
    }

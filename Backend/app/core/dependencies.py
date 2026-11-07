from uuid import UUID

from fastapi import Depends, Header, HTTPException
from jose import JWTError
from sqlalchemy.orm import Session

from app.core.auth import decode_token
from app.db.dependencies import get_db
from app.models.user import User


def get_current_user(
    authorization: str | None = Header(None),
    db: Session = Depends(get_db)
):
    if not authorization:
        raise HTTPException(
            status_code=401,
            detail="Authorization header missing"
        )

    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Invalid authorization header"
        )

    token = authorization[len("Bearer "):].strip()

    # Antes un token caducado o mal formado acababa en error 500
    try:
        payload = decode_token(token)
    except JWTError:
        raise HTTPException(status_code=401, detail="Sesión caducada o no válida")

    if payload.get("typ") == "pos":
        raise HTTPException(status_code=401, detail="Este es un token de TPV: entra con tu cuenta")

    try:
        user_id = UUID(str(payload.get("sub")))
    except ValueError:
        raise HTTPException(status_code=401, detail="Sesión no válida")

    user = db.get(User, user_id)

    if not user:
        raise HTTPException(
            status_code=401,
            detail="User not found"
        )

    if not user.is_active:
        raise HTTPException(status_code=403, detail="Cuenta desactivada")

    return user

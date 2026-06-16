from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.core.auth import get_user_id_from_token
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

    token = authorization.replace(
        "Bearer ",
        ""
    )

    user_id = get_user_id_from_token(
        token
    )

    user = db.query(User).filter(
        User.id == user_id
    ).first()

    if not user:
        raise HTTPException(
            status_code=401,
            detail="User not found"
        )

    return user
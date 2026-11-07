from datetime import datetime, timedelta, timezone

from jose import jwt

from app.core.config import (
    SECRET_KEY,
    ALGORITHM,
)


def create_access_token(
    user_id: str
):
    expire = datetime.now(timezone.utc) + timedelta(days=7)

    payload = {
        "sub": user_id,
        "exp": expire
    }

    return jwt.encode(
        payload,
        SECRET_KEY,
        algorithm=ALGORITHM
    )

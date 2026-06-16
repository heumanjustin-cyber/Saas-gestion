from jose import jwt

from app.core.config import (
    SECRET_KEY,
    ALGORITHM,
)


def decode_token(token: str):
    return jwt.decode(
        token,
        SECRET_KEY,
        algorithms=[ALGORITHM]
    )


def get_user_id_from_token(
    token: str
):
    payload = decode_token(token)

    return payload["sub"]
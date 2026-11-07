"""Contraseñas con scrypt (sal aleatoria por usuario, coste de memoria contra ataques con GPU).

Antes se guardaban como SHA-256 sin sal: dos usuarios con la misma contraseña tenían el mismo
hash y se podían romper con tablas precalculadas. Los hashes antiguos siguen valiendo para entrar
y se convierten a scrypt en el siguiente inicio de sesión (ver needs_rehash).
"""
import base64
import hashlib
import hmac
import secrets

_N, _R, _P = 2 ** 14, 8, 1  # ~16 MB y ~50 ms por intento
_PREFIX = "scrypt$"


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    dk = hashlib.scrypt(password.encode(), salt=salt, n=_N, r=_R, p=_P, dklen=32)
    return f"{_PREFIX}{_N}${_R}${_P}${base64.b64encode(salt).decode()}${base64.b64encode(dk).decode()}"


def verify_password(
    plain_password: str,
    hashed_password: str
) -> bool:
    if not hashed_password:
        return False
    if hashed_password.startswith(_PREFIX):
        try:
            _, n, r, p, salt_b64, dk_b64 = hashed_password.split("$")
            expected = base64.b64decode(dk_b64)
            test = hashlib.scrypt(plain_password.encode(), salt=base64.b64decode(salt_b64), n=int(n), r=int(r),
                                  p=int(p), dklen=len(expected))
        except (ValueError, TypeError):
            return False
        return hmac.compare_digest(test, expected)
    # Formato antiguo (SHA-256 sin sal)
    return hmac.compare_digest(hashlib.sha256(plain_password.encode()).hexdigest(), hashed_password)


def needs_rehash(hashed_password: str) -> bool:
    return not (hashed_password or "").startswith(_PREFIX)


# Para comparar en tiempo constante cuando el email no existe (no revela qué emails hay registrados)
DUMMY_HASH = hash_password(secrets.token_urlsafe(16))

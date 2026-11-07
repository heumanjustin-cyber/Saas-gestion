from dotenv import load_dotenv
import os
import re

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
SECRET_KEY = os.getenv("SECRET_KEY")
# Solo firmas HMAC: nunca "none" ni algoritmos que no esperamos
ALGORITHM = os.getenv("ALGORITHM") or "HS256"
if ALGORITHM not in ("HS256", "HS384", "HS512"):
    raise RuntimeError(f"ALGORITHM no permitido: {ALGORITHM!r} (usa HS256)")
if not SECRET_KEY:
    print("AVISO: falta SECRET_KEY: no se podrán firmar sesiones.")
elif len(SECRET_KEY) < 32:
    print("AVISO: SECRET_KEY es corta; usa al menos 32 caracteres aleatorios.")

# URL pública del backend: con ella se imprimen los QR de mesas y displays
# (https://<dominio>/q/<código>). Si falta, se usa la de la petición.
PUBLIC_BASE_URL = (os.getenv("PUBLIC_BASE_URL") or "").rstrip("/")

# Identidad del sistema informático de facturación (SIF) para Verifactu.
# Los rellena el productor del software (BUHOSS) antes de emitir en producción.
SIF_PRODUCER_NAME = os.getenv("BUHOS_SIF_PRODUCER_NAME", "BUHOSS")
SIF_PRODUCER_NIF = os.getenv("BUHOS_SIF_PRODUCER_NIF", "")
SIF_NAME = os.getenv("BUHOS_SIF_NAME", "BUHOSS TPV")
SIF_ID = os.getenv("BUHOS_SIF_ID", "BT")[:2]
SIF_VERSION = os.getenv("BUHOS_SIF_VERSION", "1.0.0")


def _mask_password(url: str | None) -> str | None:
    if not url:
        return url
    return re.sub(r"://([^:/@]+):([^@]+)@", r"://\1:***@", url)


# Antes se imprimía la URL completa con la contraseña de la base de datos.
print("DATABASE_URL:", _mask_password(DATABASE_URL))

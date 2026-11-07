"""Deja Ankara Kebab listo en BUHOS: ficha, carta (42 platos), mesas con QR, piezas QR, caja y modo pruebas.

    python -m scripts.seed_ankara --email dueno@ankara.es --password 'algo-largo'

Con --nif y --razon-social se configuran los datos fiscales reales; sin ellos se usa
un perfil de PRUEBAS (los tickets salen marcados «sin validez fiscal»).
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.core.config import PUBLIC_BASE_URL
from app.core.security import hash_password
from app.db.init_db import create_tables
from app.db.session import SessionLocal
from app.models.company import Company
from app.models.dining import QrCode
from app.models.fiscal import FiscalProfile
from app.models.menu import MenuCategory
from app.models.pos import PosRegister
from app.models.user import User
from app.models.venue import VenueProfile
from app.services import nif as nif_check
from app.services import qr_service
from app.services.access_service import create_default_roles, create_owner_membership
from app.services.studio42_import import apply_translations, import_carta, import_hub

SEED = Path(__file__).resolve().parent.parent / "seed" / "ankara"
SLUG = "ankara-kebab"
PIECES = [  # una pieza = un QR propio con sus estadísticas
    ("display", "Display de la barra"),
    ("door", "Vinilo de la puerta"),
    ("keychain", "Llavero"),
    ("bag", "Bolsa de reparto"),
]


def load(name: str) -> dict:
    return json.loads((SEED / name).read_text(encoding="utf-8"))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--email", required=True)
    ap.add_argument("--password", required=True)
    ap.add_argument("--nombre", default="Dueño de Ankara Kebab")
    ap.add_argument("--nif", help="NIF real del titular (si no, perfil de pruebas)")
    ap.add_argument("--razon-social", dest="legal_name")
    ap.add_argument("--reset-carta", action="store_true", help="vuelve a importar la carta aunque ya exista")
    args = ap.parse_args()
    if len(args.password) < 8:
        raise SystemExit("La contraseña debe tener al menos 8 caracteres.")

    create_tables()
    with SessionLocal() as db:
        user = db.query(User).filter(User.email == args.email).first()
        if not user:
            user = User(email=args.email, hashed_password=hash_password(args.password), full_name=args.nombre)
            db.add(user)
            db.flush()
        company = db.query(Company).filter(Company.slug == SLUG).first()
        new_company = company is None
        if new_company:
            company = Company(name="Ankara Kebab", slug=SLUG, owner_user_id=user.id, country="ES",
                              timezone="Europe/Madrid", currency="EUR", language="es")
            db.add(company)
            db.commit()
            create_default_roles(db=db, company=company)
            create_owner_membership(db=db, company=company, user=user)
        elif company.owner_user_id != user.id:
            raise SystemExit(f"{SLUG} ya existe y es de otro usuario.")

        print("Ficha:", import_hub(db, company, load("hub_studio42.json"))["venue"])
        venue = db.query(VenueProfile).filter(VenueProfile.company_id == company.id).one()
        venue.description = ("Kebab, dürüm, lahmacun, pedrata y menús halal en Logroño desde 2018. "
                             "Pide desde el móvil: a tu mesa, para recoger o a domicilio.")
        venue.tags = ["halal"]
        venue.languages = ["es", "en", "fr"]
        venue.takeaway_enabled = True
        venue.dine_in_enabled = True
        venue.prep_time_minutes = 15
        venue.free_tap_water = True

        has_menu = db.query(MenuCategory.id).filter(MenuCategory.company_id == company.id).first() is not None
        if not has_menu or args.reset_carta:
            stats = import_carta(db, company, load("carta_studio42.json"), load("allergen_hints.json"))
            print("Carta:", stats)
            print("Traducciones EN/FR:", apply_translations(db, company.id, load("translations.json")))

        if not db.query(FiscalProfile).filter(FiscalProfile.company_id == company.id).first():
            if args.nif:
                if not nif_check.is_valid_nif(args.nif) or not args.legal_name:
                    raise SystemExit("NIF no válido o falta --razon-social.")
                fp = FiscalProfile(company_id=company.id, nif=nif_check.normalize(args.nif), legal_name=args.legal_name,
                                   address=venue.address, postal_code=venue.postal_code, city=venue.city,
                                   province=venue.province, environment="test")
            else:
                fp = FiscalProfile(company_id=company.id, nif="00000000T", legal_name="Ankara Kebab (DATOS DE PRUEBA)",
                                   address=venue.address, postal_code=venue.postal_code, city=venue.city,
                                   province=venue.province, environment="test")
            db.add(fp)

        if not db.query(PosRegister).filter(PosRegister.company_id == company.id).first():
            db.add(PosRegister(company_id=company.id, name="Caja 1"))
        kinds = {q.kind for q in db.query(QrCode).filter(QrCode.company_id == company.id).all()}
        for kind, label in PIECES:
            if kind not in kinds:
                db.add(QrCode(company_id=company.id, code=qr_service.new_code(db), kind=kind, label=label,
                              target="review" if kind == "bag" else "menu"))
        db.commit()

        base = PUBLIC_BASE_URL or "http://localhost:8000"
        print("\nAnkara Kebab en BUHOS")
        print(f"  Carta y pedidos:  {base}/r/{SLUG}")
        print(f"  TPV:              {base}/app/tpv   (entra con {args.email})")
        print(f"  Cocina:           {base}/app/cocina")
        print(f"  Hoja de QR:       GET {base}/my/venues/{company.id}/qr-sheet (con tu token)")
        for q in db.query(QrCode).filter(QrCode.company_id == company.id).order_by(QrCode.kind, QrCode.label).all():
            print(f"    {q.label:<22} {base}/q/{q.code}")


if __name__ == "__main__":
    main()

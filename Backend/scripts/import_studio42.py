"""Migra un cliente de Studio 42 a BUHOSS.

    python -m scripts.import_studio42 --slug ankara-kebab \
        --hub https://studio42.es/c/ankara-kebab.json --carta carta.json

--hub acepta una URL o un fichero. --carta es el objeto `window.PEDIDO_VE` en JSON; se obtiene
abriendo su web de pedidos y escribiendo en la consola del navegador:
    copy(JSON.stringify(window.PEDIDO_VE))
"""
from __future__ import annotations

import argparse
import json
import urllib.request

from app.db.init_db import create_tables
from app.db.session import SessionLocal
from app.models.company import Company
from app.services.studio42_import import import_carta, import_hub


def load(src: str) -> dict:
    if src.startswith("https://"):
        with urllib.request.urlopen(src, timeout=20) as r:  # noqa: S310 (URL https la da quien migra)
            return json.loads(r.read().decode("utf-8"))
    with open(src, encoding="utf-8") as f:
        return json.load(f)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--slug", required=True, help="slug de la empresa en BUHOSS (debe existir)")
    ap.add_argument("--hub", help="URL o fichero del JSON del hub (studio42.es/c/<código>.json)")
    ap.add_argument("--carta", help="fichero JSON con window.PEDIDO_VE")
    ap.add_argument("--alergenos", help="JSON {id_plato: [alérgenos], 'option:<nombre>': [...]}")
    args = ap.parse_args()
    create_tables()
    with SessionLocal() as db:
        company = db.query(Company).filter(Company.slug == args.slug).first()
        if not company:
            raise SystemExit(f"No existe la empresa {args.slug!r}: créala primero (POST /companies).")
        if args.hub:
            print("Ficha:", import_hub(db, company, load(args.hub)))
        if args.carta:
            hints = load(args.alergenos) if args.alergenos else None
            print("Carta:", import_carta(db, company, load(args.carta), hints))
        db.commit()
    print("Listo. Revisa los alérgenos plato a plato con el dueño (quedan marcados «sin confirmar»).")


if __name__ == "__main__":
    main()
